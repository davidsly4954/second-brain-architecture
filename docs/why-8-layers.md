# Why 8 Layers?

## The Knowledge Persistence Problem

AI coding assistants are stateless by default. Every session starts fresh. Long conversations get compacted, losing detail. The assistant that helped you refactor the auth module yesterday doesn't remember doing it today.

People try to solve this in different ways:
- **RAG (retrieval-augmented generation)** — embed documents, search by similarity
- **Knowledge graphs** — structured relationships between entities
- **Memory files** — save facts to disk, load them later
- **Session logs** — keep raw transcripts

Each approach captures some knowledge but misses other types. The question isn't "which one is best?" — it's "what does each one miss?"

## The Coverage Gap Analysis

| Knowledge Type | RAG | Graph | Memory | Logs |
|---------------|-----|-------|--------|------|
| Code structure (functions, imports) | Partial | **Yes** | No | No |
| Cross-file relationships | No | **Yes** | No | No |
| Community/module detection | No | Partial | No | No |
| Session history (what was discussed) | No | **Yes** | Partial | **Yes** |
| Human-written context (architecture, decisions) | **Yes** | No | Partial | No |
| Semantic similarity ("things like X") | **Yes** | No | No | No |
| Persistent facts (preferences, project state) | No | No | **Yes** | No |
| Complete transcripts (nothing lost) | No | No | No | **Yes** |
| Auto-updates on code changes | No | Partial | No | No |

No single layer covers more than 3-4 of these knowledge types. That's why we use 8.

## Why Not Fewer?

**"Can't I just use RAG?"**

RAG (embedding + vector search) is great for finding *similar content* but it has no concept of *structure*. It can't tell you "what functions call the auth middleware" or "what sessions discussed the database schema in chronological order." It treats everything as flat text chunks.

**"Can't I just use a knowledge graph?"**

A knowledge graph captures structure beautifully but it can't do semantic similarity search. If you ask "find things related to authentication," a graph needs an exact node named "authentication." A vector search finds related concepts even if they use different words (login, session, JWT, OAuth).

**"Can't I just use memory files?"**

Memory files are the simplest and most impactful layer for day-to-day work. But they only capture what the AI explicitly decides to save. They miss code structure, session history, semantic relationships, and the complete transcript.

**"Can't I combine 2-3 of these?"**

You can, and you should start there. The minimum viable knowledge system is:
1. **Memory files** (Layer 6) — survives compaction, zero setup
2. **Code Review Graph** (Layer 2) — live code understanding
3. **Neo4j** (Layer 3) — session history

That gives you persistence + code awareness + session memory. Add the other layers as the value becomes clear.

## Why Not More?

8 layers is already complex. Each additional layer adds:
- Configuration and maintenance burden
- Potential failure points
- Cognitive overhead (which layer has what?)

The 8 layers we chose are the minimal set where each layer fills a gap no other layer covers. Adding a 9th would either duplicate an existing layer's function or capture knowledge that isn't valuable enough to justify the complexity.

## The Auto-Update Principle

The key design principle is: **layers that need frequent updates must be automatic.**

| Layer | Update Frequency | Mechanism |
|-------|-----------------|-----------|
| Code Review Graph | Every file edit | Hook (automatic) |
| Neo4j | Every session | Watcher + timer (automatic) |
| Obsidian MCP | Every vault edit | SSE daemon (automatic) |
| Memory Files | Every conversation | Claude auto-memory (automatic) |
| Session Logs | Every message | Claude Code (automatic) |
| Session Watcher | Always running | systemd (automatic) |
| Graphify | Occasionally | Manual (intentional) |
| Qdrant | Occasionally | Manual (intentional) |

The two manual layers (Graphify and Qdrant) are intentionally manual because:
- **Graphify** does deep analysis with community detection — it takes minutes and you want the full picture, not incremental fragments
- **Qdrant** depends on the content of Obsidian and memory files — seeding after major additions is more efficient than re-embedding on every small change

## Cost

The entire system runs locally with zero API costs for the knowledge layers themselves:
- **Neo4j Community Edition** — free, open source
- **Qdrant** — free, local storage
- **basic-memory** — free, open source
- **code-review-graph** — free, open source
- **graphify** — free, open source
- **inotifywait** — free, part of inotify-tools
- **systemd** — built into Linux

The only costs are:
- Docker resources for Neo4j (~2GB RAM)
- Disk space for embeddings and graph databases (~500MB-2GB depending on codebase size)
- One-time embedding computation when seeding Qdrant (~30 seconds for a few hundred documents)
