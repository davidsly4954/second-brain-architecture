# Architecture Overview

```mermaid
graph TB
    subgraph "Static Analysis"
        L1["Layer 1: Graphify<br/>Community detection<br/>Cross-file connections<br/><i>Manual trigger</i>"]
    end

    subgraph "Live Code Tracking"
        L2["Layer 2: Code Review Graph<br/>AST database (SQLite)<br/>Functions, imports, calls<br/><i>Auto: hooks on edit</i>"]
    end

    subgraph "Session Intelligence"
        L3["Layer 3: Neo4j<br/>Session history graph<br/>Topics, tools, cross-session links<br/><i>Auto: timer + watcher</i>"]
        L7["Layer 7: Session Logs<br/>Full JSONL transcripts<br/>Complete archive<br/><i>Auto: Claude writes</i>"]
        L8["Layer 8: Session Watcher<br/>inotifywait detection<br/>Debounced reimport<br/><i>Auto: file events</i>"]
    end

    subgraph "Knowledge Base"
        L4["Layer 4: Obsidian MCP<br/>Human-written notes<br/>Architecture, decisions, context<br/><i>Auto: SSE daemon</i>"]
        L6["Layer 6: Memory Files<br/>Persistent facts<br/>Preferences, project state<br/><i>Auto: Claude memory</i>"]
    end

    subgraph "Semantic Layer"
        L5["Layer 5: Qdrant Vectors<br/>Embeddings of notes + memory<br/>Similarity search<br/><i>Manual: seed script</i>"]
    end

    %% Data flows
    L2 -->|"signal reimport"| L3
    L7 -->|"JSONL files"| L8
    L8 -->|"triggers import"| L3
    L4 -->|"note content"| L5
    L6 -->|"memory content"| L5

    %% External triggers
    DEV["Developer Activity"] -.->|"file edits"| L2
    DEV -.->|"conversations"| L6
    DEV -.->|"conversations"| L7
    TIMER["30-min Timer"] -.->|"periodic"| L3
    VAULT["Vault Edits"] -.->|"file changes"| L4

    style L1 fill:#2d1b69,stroke:#8b5cf6,color:#fff
    style L2 fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style L3 fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style L4 fill:#1a4731,stroke:#22c55e,color:#fff
    style L5 fill:#5c2d0e,stroke:#f59e0b,color:#fff
    style L6 fill:#1a4731,stroke:#22c55e,color:#fff
    style L7 fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style L8 fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style DEV fill:#333,stroke:#888,color:#fff
    style TIMER fill:#333,stroke:#888,color:#fff
    style VAULT fill:#333,stroke:#888,color:#fff
```

## Color Legend

| Color | Meaning |
|-------|---------|
| Purple | Static analysis (run on demand) |
| Blue | Automated, event-driven |
| Green | Knowledge base (human + AI authored) |
| Orange | Semantic / embedding layer |
| Gray | External triggers |
