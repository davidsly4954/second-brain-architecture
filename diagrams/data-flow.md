# Data Flow

How information moves through the 8-layer system during a typical development session.

## Normal Development Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CC as Claude Code
    participant CRG as Code Review Graph
    participant Neo as Neo4j
    participant Mem as Memory Files
    participant Logs as Session Logs
    participant Watch as Session Watcher

    Dev->>CC: Edit a file
    CC->>CC: Write changes to disk

    par PostToolUse Hook
        CC->>CRG: update --skip-flows
        CRG->>CRG: Re-parse AST, update SQLite
        CRG-->>Neo: Signal: new data available
    end

    CC->>Logs: Append to session JSONL

    Note over Watch: inotifywait detects JSONL change
    Watch->>Watch: Start 30s debounce timer

    Dev->>CC: Ask about code structure
    CC->>CRG: Query: "what calls this function?"
    CRG-->>CC: Return call graph from SQLite

    Dev->>CC: Ask about project history
    CC->>Neo: Query: "sessions about auth?"
    Neo-->>CC: Return session nodes + topics

    CC->>Mem: Save important fact to memory

    Note over Watch: Debounce timer fires
    Watch->>Neo: Trigger reimport (make import-and-seed)
    Neo->>Neo: Parse JSONL, create session nodes
```

## Session Lifecycle

```mermaid
sequenceDiagram
    participant CC as Claude Code
    participant CRG as Code Review Graph
    participant Mem as Memory Files
    participant Logs as Session Logs
    participant Q as Qdrant

    Note over CC: Session Start
    CC->>Mem: Load MEMORY.md index
    CC->>CRG: status (SessionStart hook)

    Note over CC: Active Development
    loop Every file edit
        CC->>CRG: update --skip-flows
        CC->>Logs: Append to JSONL
    end

    Note over CC: Context approaching limit (~200K tokens)
    CC->>CC: PreToolUse hook detects threshold
    CC->>Mem: Dump key knowledge to memory files

    Note over CC: Compaction
    CC->>CC: Prior messages compressed
    CC->>Mem: Re-load MEMORY.md (knowledge survives)

    Note over CC: Session End
    CC->>CRG: Full update (Stop hook)
    CC->>Logs: Final JSONL write

    Note over Logs: Watcher detects, triggers Neo4j import
    Note over Q: Manual: run seed script if new notes added
```

## What Survives Context Compaction

| Layer | Survives? | How |
|-------|-----------|-----|
| 1. Graphify | Yes | Static files on disk — unaffected |
| 2. Code Review Graph | Yes | SQLite DB on disk — unaffected |
| 3. Neo4j | Yes | Docker volumes — unaffected |
| 4. Obsidian MCP | Yes | Vault files on disk — unaffected |
| 5. Qdrant | Yes | Vector DB on disk — unaffected |
| 6. Memory Files | **Yes, and auto-loads** | MEMORY.md reloaded after compaction |
| 7. Session Logs | Yes | JSONL on disk — raw transcript preserved |
| 8. Session Watcher | Yes | Systemd service — always running |

**The entire system is designed so that context compaction loses nothing permanent.** The conversation summary gets shorter, but all 8 layers retain their full content. Memory files are the key bridge — they load automatically and carry the most critical facts forward.
