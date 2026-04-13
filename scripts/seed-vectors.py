#!/usr/bin/env python3
"""Seed Qdrant with knowledge entries from Obsidian vault + memory files.

This script chunks markdown files by headers, generates embeddings using
sentence-transformers, and stores them in a local Qdrant collection.
The result is a semantic search layer over all your notes and memory.

Run:
    pip install qdrant-client sentence-transformers
    python scripts/seed-vectors.py

Or with uvx (no install needed):
    uvx --with qdrant-client --with sentence-transformers python scripts/seed-vectors.py

The script uses the same storage path and embedding model as the Qdrant
MCP server, so entries are immediately searchable via MCP tools.
"""

import hashlib
import re
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# ── Configuration ──────────────────────────────────────────────
# Update these paths to match your setup

QDRANT_PATH = Path.home() / ".qdrant-data" / "my-project"
COLLECTION = "my-knowledge"
OBSIDIAN_DIR = Path("/path/to/your/obsidian/vault")
MEMORY_DIR = Path.home() / ".claude" / "projects" / "my-project" / "memory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DIM = 384  # all-MiniLM-L6-v2 output dimension

# ── Chunking ───────────────────────────────────────────────────


def chunk_markdown(text: str, source: str, max_chars: int = 1000) -> list[dict]:
    """Split markdown into semantic chunks by ## headers.

    Each chunk gets metadata about its source file and section header,
    which becomes searchable payload in Qdrant.
    """
    chunks = []
    sections = re.split(r"\n(?=##\s)", text)

    for section in sections:
        section = section.strip()
        if not section or len(section) < 50:
            continue

        header_match = re.match(r"^##\s+(.+)", section)
        header = header_match.group(1) if header_match else ""

        if len(section) > max_chars:
            # Split long sections by paragraph
            paragraphs = section.split("\n\n")
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) > max_chars and current_chunk:
                    chunks.append(
                        {"text": current_chunk.strip(), "source": source, "header": header}
                    )
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para
            if current_chunk.strip():
                chunks.append(
                    {"text": current_chunk.strip(), "source": source, "header": header}
                )
        else:
            chunks.append({"text": section, "source": source, "header": header})

    return chunks


def generate_id(text: str) -> str:
    """Generate a deterministic UUID-like ID from text content."""
    h = hashlib.md5(text.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# ── Main ───────────────────────────────────────────────────────


def main():
    print("=== Qdrant Seed Script ===\n")

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Data path: {QDRANT_PATH}")

    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    client = QdrantClient(path=str(QDRANT_PATH))

    # Create or check collection
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION in collections:
        existing_count = client.count(COLLECTION).count
        print(f"Collection '{COLLECTION}' exists with {existing_count} points")
        if existing_count > 0:
            print("Already seeded. To re-seed, delete the collection first:")
            print(f"  rm -rf {QDRANT_PATH}")
            return
    else:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION}'")

    all_chunks = []

    # 1. Process Obsidian notes
    if OBSIDIAN_DIR.exists():
        print(f"\nProcessing Obsidian vault ({OBSIDIAN_DIR})...")
        for md_file in sorted(OBSIDIAN_DIR.rglob("*.md")):
            if md_file.name.startswith(".") or "Templates" in str(md_file):
                continue
            rel_path = md_file.relative_to(OBSIDIAN_DIR)
            text = md_file.read_text(errors="replace")

            # Strip YAML frontmatter
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    text = text[end + 3 :]

            chunks = chunk_markdown(text, source=f"obsidian/{rel_path}")
            all_chunks.extend(chunks)
            if chunks:
                print(f"  {rel_path}: {len(chunks)} chunks")
    else:
        print(f"Obsidian vault not found at {OBSIDIAN_DIR} — skipping")

    # 2. Process memory files
    if MEMORY_DIR.exists():
        print(f"\nProcessing memory files ({MEMORY_DIR})...")
        for md_file in sorted(MEMORY_DIR.glob("*.md")):
            if md_file.name == "MEMORY.md":
                continue  # Index file, skip
            text = md_file.read_text(errors="replace")

            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    text = text[end + 3 :]

            if len(text.strip()) > 50:
                all_chunks.append(
                    {
                        "text": text.strip()[:1500],
                        "source": f"memory/{md_file.name}",
                        "header": md_file.stem.replace("_", " "),
                    }
                )
                print(f"  {md_file.name}")
    else:
        print(f"Memory directory not found at {MEMORY_DIR} — skipping")

    print(f"\nTotal chunks to embed: {len(all_chunks)}")
    if not all_chunks:
        print("Nothing to embed. Check your paths.")
        return

    # Embed
    print("Embedding...")
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"Embedded {len(embeddings)} chunks")

    # Store
    print("Storing in Qdrant...")
    points = []
    for chunk, embedding in zip(all_chunks, embeddings):
        point_id = generate_id(chunk["text"][:200] + chunk["source"])
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "header": chunk["header"],
                    "type": "obsidian" if chunk["source"].startswith("obsidian/") else "memory",
                },
            )
        )

    # Upsert in batches
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=COLLECTION, points=batch)

    final_count = client.count(COLLECTION).count
    print(f"\n=== Seed Complete ===")
    print(f"  Collection: {COLLECTION}")
    print(f"  Points stored: {final_count}")
    print(f"  Storage: {QDRANT_PATH}")

    # Quick test search
    print('\nTest search: "authentication system"')
    query_vec = model.encode("authentication system").tolist()
    results = client.query_points(
        collection_name=COLLECTION, query=query_vec, limit=3
    )
    for hit in results.points:
        src = hit.payload.get("source", "")
        hdr = hit.payload.get("header", "")
        print(f"  [{hit.score:.3f}] {src} — {hdr}")


if __name__ == "__main__":
    main()
