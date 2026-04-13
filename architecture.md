# Architecture Deep Dive

Each layer captures a specific type of knowledge that the other layers miss. This document explains what each layer does, how it works, and why it exists.

---

## Layer 1: Graphify — Static Codebase Knowledge Graph

**What it is:** A CLI tool that reads your entire codebase and builds a knowledge graph with community detection. Outputs interactive HTML visualization, GraphRAG-ready JSON, and a plain-language report.

**What it captures:**
- Every entity in your code (functions, classes, modules, variables)
- Relationships between entities (imports, calls, inheritance, references)
- Community structure — clusters of related code that form natural modules
- Cross-file connections you wouldn't notice by reading code linearly

**Storage:** `graphify-out/` directory containing `graph.json`, `GRAPH_REPORT.md`, and interactive HTML

**Update mechanism:** Manual — run `/graphify .` when you want a fresh snapshot. This is intentional: Graphify does deep analysis with community detection that takes minutes, not seconds. You want a complete picture, not incremental updates.

**Why it exists:** Code Review Graph (Layer 2) tracks live changes but doesn't do community detection or cross-file relationship analysis. Graphify provides the "big picture" view that helps you understand architecture before making changes.

**Example use:**
```
"What are the main modules in this codebase and how do they relate?"
→ Check GRAPH_REPORT.md for community summaries
→ Open the interactive HTML to explore visually
```

---

## Layer 2: Code Review Graph — Live AST Tracking

**What it is:** An MCP server that maintains a SQLite database of your code's abstract syntax tree. Updates incrementally on every file edit via Claude Code hooks.

**What it captures:**
- Functions, classes, methods with their signatures
- Import relationships and dependency chains
- Call relationships between functions
- File-level dependency graph
- Changes since last update (what moved, what broke)

**Storage:** `.code-review-graph/` directory containing SQLite database

**Update mechanism:** Automatic — three hooks keep it current:
1. `PostToolUse` (Edit/Write) — incremental update after every file change
2. `SessionStart` — brief status check at session start
3. `Stop` — full update when session ends

**Why it exists:** Graphify gives you the big picture but it's a static snapshot. Code Review Graph tracks every edit in real time, so the AI assistant always knows the current state of the code — what functions exist, what calls what, what changed in the last edit.

**Example use:**
```
"What functions call the authentication middleware?"
→ Code Review Graph can answer this from its live AST database
```

---

## Layer 3: Neo4j + Context Graph — Session History

**What it is:** A Neo4j graph database that stores the history of all your AI coding sessions — what was discussed, what topics came up, what tools were used, and how sessions connect to each other.

**What it captures:**
- Every CLI session and web conversation (as nodes)
- Topics discussed in each session
- Tools and MCP servers used
- Cross-session links (same topic across different sessions)
- Temporal relationships (session ordering)

**Storage:** Neo4j Docker container with persistent volumes

**Update mechanism:** Automatic, three triggers:
1. **Session watcher** (Layer 8) — inotifywait detects new/changed JSONL files, triggers reimport
2. **30-minute systemd timer** — periodic reimport catches anything the watcher missed
3. **Hook signal** — PostToolUse hook signals that new data exists

**Why it exists:** Memory files (Layer 6) store facts but not the *flow* of conversations. Neo4j preserves the full structure: "In session X, we discussed authentication, which led to session Y where we refactored the auth module." This temporal context is invisible to the other layers.

**Example use:**
```
"What sessions have we had about the database schema?"
→ Query Neo4j for sessions linked to the 'database' or 'schema' topic nodes
```

---

## Layer 4: Obsidian MCP — Human Knowledge Base

**What it is:** An MCP server (basic-memory) that indexes your Obsidian vault and makes it searchable by the AI assistant. Runs as an SSE daemon that continuously watches for vault changes.

**What it captures:**
- Architecture decision records
- Infrastructure documentation
- Business context and strategy notes
- Meeting notes, research, reference material
- Anything you write in your Obsidian vault

**Storage:** Obsidian vault directory (markdown files) + basic-memory SQLite index

**Update mechanism:** Automatic — the basic-memory SSE daemon watches the vault directory and re-indexes when files change. No manual action needed.

**Why it exists:** Code graphs and session history capture *what happened in code*. But much of the context for good decisions lives outside code — in architecture docs, business requirements, infrastructure notes. Obsidian MCP bridges that gap.

**Important:** The MCP server must use SSE transport (not stdio) when running as a systemd daemon. Stdio requires a connected client on stdin/stdout — without one, the process exits immediately and systemd restart-loops it. This was a hard-won lesson.

**Example use:**
```
"What's our deployment process?"
→ basic-memory searches the vault, finds the Deployment Guide note
```

---

## Layer 5: Qdrant Vectors — Semantic Search

**What it is:** A local Qdrant vector database containing embeddings of all Obsidian notes and memory files. Enables semantic similarity search across all text content.

**What it captures:**
- Chunked embeddings of every Obsidian note
- Chunked embeddings of every memory file
- Metadata (source file, section header, content type)

**Storage:** Local Qdrant storage directory

**Update mechanism:** Manual — run the seed script after adding significant new content to Obsidian or memory files. The script is idempotent (re-running it updates existing vectors).

**Why it exists:** The other layers search by exact keywords or graph traversal. Qdrant enables *semantic* search — "find things related to authentication" will match notes about login, sessions, JWT, OAuth, even if those exact words aren't in the query. This catches conceptual connections that keyword search misses.

**Example use:**
```
"What do we know about rate limiting?"
→ Qdrant finds semantically related content across all notes and memory files,
  even if they don't use the phrase "rate limiting"
```

---

## Layer 6: Memory Files — Persistent Facts

**What it is:** Claude Code's built-in auto-memory system. Markdown files with YAML frontmatter, stored in a project-specific directory. An index file (MEMORY.md) is loaded into every conversation automatically.

**What it captures:**
- User preferences and working style
- Feedback on approach (what to do/avoid)
- Project context (goals, status, decisions)
- Reference pointers to external systems
- Key facts that should survive context compaction

**Storage:** `~/.claude/projects/<project>/memory/` directory

**Update mechanism:** Automatic — Claude Code creates and updates memory files during conversations when it learns important information. MEMORY.md (the index) loads automatically at the start of every session.

**Why it exists:** This is the **most impactful layer for daily work.** When Claude Code compacts a long conversation (at ~200K tokens), most context is lost. Memory files survive compaction because they're loaded from disk, not from conversation history. They're the bridge between sessions.

**Example use:**
```
"Remember that we decided to use PostgreSQL instead of MongoDB"
→ Claude saves this as a project memory file
→ Next session, this fact is automatically available
```

---

## Layer 7: Session Logs — Full Transcript Archive

**What it is:** A Go binary that serves session JSONL files over HTTP, making them accessible to the AI assistant and other tools. Claude Code writes these files automatically.

**What it captures:**
- Complete transcripts of every coding session
- Every tool call, every response, every edit
- Timestamps, token counts, model information
- The raw, uncompacted record of everything that happened

**Storage:** JSONL files on disk + HTTP server for access

**Update mechanism:** Automatic — Claude Code writes to JSONL files in real time. The HTTP server makes them browsable.

**Why it exists:** When Claude Code compacts a conversation, the original messages are summarized but the JSONL file on disk retains everything. This is the archive of last resort — if something was discussed 3 sessions ago and isn't in memory or Neo4j, the raw transcript is still there.

**Example use:**
```
"What exactly did we discuss about the API design 2 weeks ago?"
→ Session logs have the complete transcript, even if that conversation was compacted
```

---

## Layer 8: Session Watcher — Auto-Import Pipeline

**What it is:** An inotifywait-based systemd service that watches for new or changed session JSONL files and triggers Neo4j reimport when they're detected.

**What it captures:** Nothing directly — it's the automation glue that connects Layer 7 (session logs) to Layer 3 (Neo4j).

**Storage:** No storage of its own — triggers imports into Neo4j

**Update mechanism:** Automatic — inotifywait fires on `close_write` events for JSONL files, with a 30-second debounce to batch rapid changes.

**Why it exists:** Without this, you'd have to manually run the Neo4j import after every session. The watcher makes the whole system truly hands-off — finish a coding session, and within 30 seconds the session is searchable in Neo4j.

**Example use:**
```
No direct use — it runs silently in the background.
You know it's working when new sessions appear in Neo4j
without you doing anything.
```

---

## Layer Interaction Matrix

| Layer | Feeds Into | Fed By | Trigger |
|-------|-----------|--------|---------|
| 1. Graphify | (standalone) | Codebase files | Manual |
| 2. Code Review Graph | Layer 3 (signals) | File edits (hooks) | Auto: PostToolUse |
| 3. Neo4j | (queryable) | Layers 2, 7, 8 | Auto: timer + watcher |
| 4. Obsidian MCP | Layer 5 (embeddings) | Vault file changes | Auto: SSE daemon |
| 5. Qdrant | (queryable) | Layers 4, 6 | Manual: seed script |
| 6. Memory Files | Layer 5 (embeddings) | Conversations | Auto: Claude auto-memory |
| 7. Session Logs | Layer 8 (detection) | Claude Code | Auto: JSONL writes |
| 8. Session Watcher | Layer 3 (reimport) | Layer 7 (file changes) | Auto: inotifywait |
