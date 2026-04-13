# Lessons Learned

Hard-won knowledge from building and operating the 8-layer knowledge graph system. These lessons came from real production use, not theory.

---

## Mistake: stdio Transport for MCP Daemons

**What happened:** We configured the Obsidian vault indexer (basic-memory) as a systemd service using the default stdio MCP transport. The service accumulated 769 restarts.

**Root cause:** stdio transport requires a connected client on stdin/stdout. As a systemd daemon, no client exists. The process starts, finds no client, exits. systemd restarts it. Repeat 769 times.

**Fix:** Switch to SSE (Server-Sent Events) transport: `--transport sse --port 8765`. SSE runs as an HTTP server that stays alive independently of any client connection.

**Lesson:** Any MCP server running as a daemon (systemd, Docker, background process) must use SSE or streamable-http transport. Only use stdio when the MCP server is launched by and connected to a specific client process.

---

## Mistake: Redundant Hooks

**What happened:** Two different hooks both triggered `code-review-graph update --skip-flows` on the same PostToolUse Edit/Write event. Every file edit ran the same AST update twice, wasting 2-5 seconds per edit.

**Root cause:** One hook was added during initial setup, the other was added later when we forgot the first existed. No deduplication check.

**Fix:** Audit the hook chain end-to-end. Each event should trigger each action exactly once.

**Lesson:** Before adding a new hook, grep your settings.json for the command you're about to add. Hook chains get complex fast — document what each hook does and why.

---

## Mistake: Unused Signal Files

**What happened:** The post-tool-use hook wrote a signal file (`/tmp/neo4j-reimport-signal`) intending for something to watch for it and trigger a reimport. But the session watcher uses inotifywait on JSONL files, and the timer runs on a schedule. Nothing watches the signal file.

**Root cause:** The signal file was added speculatively during development ("something will read this later") but the actual implementation used a different signaling mechanism.

**Fix:** Remove the dead signal file touch. The session watcher and timer handle all reimport triggers.

**Lesson:** Don't add IPC mechanisms speculatively. Build the consumer first, then add the producer.

---

## Surprise: Memory Files Are the MVP

We expected Neo4j (session history) or the code review graph (live AST) to be the most valuable layers. In practice, **memory files (Layer 6) are the most impactful for day-to-day work.**

Why:
- They load automatically at the start of every session
- They survive context compaction (the single biggest context-loss event)
- They capture *decisions* and *preferences*, not just *state*
- The AI reads them before doing anything, so they influence every response

The other layers are queried on demand. Memory files influence behavior passively and continuously.

---

## Surprise: Compaction Is the Real Enemy

We initially worried about cross-session knowledge loss — "the AI won't remember what we did yesterday." That's solved by Neo4j and session logs.

The harder problem is **within-session context loss from compaction.** When a conversation hits ~200K tokens, Claude Code compresses prior messages into a summary. Details are lost. Technical decisions evaporate.

The context-aware sync hook (which fires when the JSONL file approaches ~3MB) was our response: prompt the AI to dump critical knowledge to memory files *before* compaction happens. This turns ephemeral conversation context into persistent facts.

---

## Surprise: Auto-Updates Are Non-Negotiable

Early versions required manual updates for several layers. We'd forget. The data would go stale. Then when we queried a layer, the results were outdated and we'd lose trust in the system.

The rule now is: **if a layer is queried frequently, it must auto-update.** The two manual layers (Graphify and Qdrant) are queried infrequently — Graphify for major architecture reviews, Qdrant when adding significant new content.

---

## Performance: Neo4j Import Is the Bottleneck

The 30-minute timer + session watcher both trigger `make import-and-seed`, which parses all session JSONL files and updates Neo4j. On a large project with many sessions, this can take 30-60 seconds.

The debounce in the session watcher (30 seconds) is essential. Without it, rapid file writes during an active session would trigger dozens of imports, each one taking 30+ seconds, creating a backlog that never catches up.

---

## Performance: Qdrant Seeding Is Fast

We expected embedding hundreds of documents to be slow. With `all-MiniLM-L6-v2` (a small, fast model), seeding a few hundred documents takes about 30 seconds on CPU. The batch size of 32 and the 384-dimension vectors keep memory usage under 500MB.

For most projects, re-seeding from scratch is faster than trying to do incremental updates. The script is idempotent by design.

---

## Architecture: Start with 3 Layers

If you're building this from scratch, don't try to set up all 8 layers at once. Start with:

1. **Memory Files** (Layer 6) — zero setup, built into Claude Code
2. **Code Review Graph** (Layer 2) — `pip install code-review-graph`, add one hook
3. **Neo4j** (Layer 3) — `docker compose up`, install the timer

These three give you persistence + code awareness + session memory. Add the other layers one at a time as you feel the gaps.

The order we recommend adding the rest:
4. Obsidian MCP (Layer 4) — if you have an Obsidian vault
5. Session Logs + Watcher (Layers 7+8) — for full transcript archive
6. Qdrant (Layer 5) — when you need semantic search
7. Graphify (Layer 1) — when you want the big-picture architecture view
