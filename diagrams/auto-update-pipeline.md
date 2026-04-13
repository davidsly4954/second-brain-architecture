# Auto-Update Pipeline

The system uses Claude Code hooks, systemd timers, and filesystem watchers to keep 6 of 8 layers current without any manual intervention.

## Trigger Chain

```mermaid
flowchart LR
    subgraph "Claude Code Events"
        E1[File Edit<br/>PostToolUse]
        E2[Session Start<br/>SessionStart]
        E3[Session End<br/>Stop]
        E4[Context Threshold<br/>PreToolUse]
    end

    subgraph "Hook Scripts"
        H1[post-tool-use.sh]
        H2[context-aware-sync.sh]
        H3[protect-files.sh]
    end

    subgraph "Layers Updated"
        L2[Layer 2: Code Review Graph]
        L3[Layer 3: Neo4j]
        L6[Layer 6: Memory Files]
    end

    subgraph "Background Services"
        S1[Session Watcher<br/>inotifywait]
        S2[Reimport Timer<br/>30 min]
    end

    E1 --> H1 --> L2
    H1 -->|signal| L3
    E2 --> L2
    E3 --> L2
    E4 --> H2 -->|prompt dump| L6
    E1 --> H3

    S1 -->|debounced| L3
    S2 -->|periodic| L3

    style L2 fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style L3 fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style L6 fill:#1a4731,stroke:#22c55e,color:#fff
```

## Hook Configuration

Hooks are defined in your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": ".claude/hooks/post-tool-use.sh"
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "command": ".claude/hooks/protect-files.sh"
      },
      {
        "matcher": ".*",
        "command": ".claude/hooks/context-aware-sync.sh"
      }
    ],
    "SessionStart": [
      {
        "command": "code-review-graph status"
      }
    ],
    "Stop": [
      {
        "command": "code-review-graph update"
      }
    ]
  }
}
```

## Trigger Reference Table

| Event | Hook/Service | Action | Layer(s) Affected | Latency |
|-------|-------------|--------|-------------------|---------|
| File edit (Edit/Write) | `post-tool-use.sh` | `code-review-graph update --skip-flows` | Layer 2 (CRG) | ~2-5s |
| File edit (Edit/Write) | `post-tool-use.sh` | Signal Neo4j reimport needed | Layer 3 (Neo4j) | Signal only |
| File edit (Edit/Write) | `protect-files.sh` | Block writes to .env/secrets | None (security gate) | <1s |
| Any tool use | `context-aware-sync.sh` | Check JSONL size, prompt knowledge dump | Layer 6 (Memory) | <1s |
| Session start | Hook | `code-review-graph status` | Layer 2 (CRG) | ~1s |
| Session end | Hook | `code-review-graph update` (full) | Layer 2 (CRG) | ~5-15s |
| JSONL file change | inotifywait (Layer 8) | Debounced reimport to Neo4j | Layer 3 (Neo4j) | 30s debounce |
| 30-minute interval | systemd timer | `make import-and-seed` | Layer 3 (Neo4j) | Periodic |
| Vault file change | basic-memory SSE | Re-index changed note | Layer 4 (Obsidian) | ~1-3s |
| Conversation learns fact | Claude auto-memory | Write/update memory file | Layer 6 (Memory) | Inline |
| Any conversation | Claude Code | Append to session JSONL | Layer 7 (Logs) | Inline |

## Manual Triggers (2 Layers)

| Layer | Command | When to Run |
|-------|---------|-------------|
| Layer 1: Graphify | `/graphify .` | After major refactoring or when you want a fresh architecture view |
| Layer 5: Qdrant | `python scripts/seed-vectors.py` | After adding new Obsidian notes or significant memory files |
