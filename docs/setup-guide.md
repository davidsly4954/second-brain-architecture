# Setup Guide

Step-by-step instructions to build the 8-layer knowledge graph for your own project.

## Prerequisites

- **Linux** (Ubuntu 22.04+ or similar — systemd user services are required)
- **Docker** and Docker Compose v2
- **Python 3.10+** with pip
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager (used by create-context-graph)
- **[pipx](https://pipx.pypa.io/)** — for installing CLI tools in isolated environments
- **Node.js 18+** with npm
- **Go 1.21+** (for claude-code-logs)
- **[Claude Code](https://claude.ai/code)** CLI installed and configured on at least one project
- **An Obsidian vault** (optional but recommended for Layer 4)

## Key Concepts

Before diving in, understand these Claude Code concepts:

- **`.mcp.json`** — A JSON config file in your **project root** that tells Claude Code which MCP (Model Context Protocol) servers to connect to. Claude Code reads this on startup and connects to each server listed. This is how the AI assistant gets access to Neo4j, Qdrant, Obsidian, etc.

- **`.claude/settings.json`** — A JSON config file in your **project root** that defines hooks (shell commands that run on events like file edits, session start/end). This is how the auto-update pipeline works.

- **Claude Code project ID** — Claude Code stores session data in `~/.claude/projects/<encoded-project-path>/`. The project ID is your project's absolute path with `/` replaced by `-` and leading `-` stripped. For example:
  - `/home/user/my-project` → `home-user-my-project`
  - Find yours with: `ls ~/.claude/projects/`

## Layer-by-Layer Setup

### Layer 1: Graphify

Install and run a one-time codebase analysis:

```bash
# Install (use pipx to keep it isolated)
pipx install graphifyy

# Run on your project directory
cd /path/to/your/project
graphify .
# Or inside Claude Code, use the skill: /graphify .

# Output goes to graphify-out/
# - graph.json (raw graph data)
# - GRAPH_REPORT.md (human-readable summary)
# - Interactive HTML visualization
```

### Layer 2: Code Review Graph

Install the MCP tool and configure hooks:

```bash
# Install
pipx install code-review-graph

# Initialize on your project
cd /path/to/your/project
code-review-graph init
code-review-graph update
```

Then add it to your project's `.mcp.json` (create this file in your project root if it doesn't exist):

```json
{
  "mcpServers": {
    "code-review-graph": {
      "command": "code-review-graph",
      "args": ["mcp"]
    }
  }
}
```

### Layer 3: Neo4j + Context Graph

Start Neo4j and set up the session importer:

```bash
# 1. Set your Neo4j password (add to ~/.bashrc to persist across reboots)
echo 'export NEO4J_PASSWORD="your-secure-password-here"' >> ~/.bashrc
source ~/.bashrc

# 2. Start Neo4j (from this repo's directory)
docker compose -f configs/docker-compose.yml up -d

# 3. Verify Neo4j is running
curl -s http://localhost:7474 | head -5
# Should return HTML — the Neo4j browser UI

# 4. Scaffold the context graph project
#    create-context-graph generates a full import pipeline with
#    a backend/, Makefile, and import scripts
pip install create-context-graph
mkdir -p ~/second-brain
cd ~/second-brain
uvx create-context-graph my-brain --init

# This creates ~/second-brain/my-brain/ with:
#   backend/          — Python import scripts
#   Makefile          — includes 'import-and-seed' target
#   docker-compose.yml (you can ignore this — we use our own Neo4j)

# 5. Import your Claude Code sessions
cd ~/second-brain/my-brain
make import-and-seed
# This parses your session JSONL files and creates nodes in Neo4j
```

Then add Neo4j to your `.mcp.json`:

```json
{
  "mcpServers": {
    "neo4j": {
      "command": "uvx",
      "args": ["mcp-neo4j"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "<your-neo4j-password>",
        "NEO4J_DATABASE": "neo4j"
      }
    }
  }
}
```

### Layer 4: Obsidian MCP (basic-memory)

Set up the vault indexer as a systemd daemon:

```bash
# 1. Install basic-memory
pipx install basic-memory

# 2. Configure it to point at your Obsidian vault
basic-memory config --project my-project --vault /path/to/your/obsidian/vault

# 3. Persist the vault path for MCP (add to ~/.bashrc)
echo 'export OBSIDIAN_VAULT_PATH="/path/to/your/obsidian/vault"' >> ~/.bashrc
source ~/.bashrc

# 4. Install the systemd service
mkdir -p ~/.config/systemd/user
cp configs/systemd/basic-memory-sync.service ~/.config/systemd/user/

# 5. Edit the service file — update the --project name
#    nano ~/.config/systemd/user/basic-memory-sync.service
#    Change "my-project" to your project name

# 6. Enable and start
systemctl --user daemon-reload
systemctl --user enable --now basic-memory-sync

# 7. Verify it's running (should show "active (running)" with 0 restarts)
systemctl --user status basic-memory-sync
```

**Important:** The service MUST use `--transport sse` (not stdio). See the service file comments for the full explanation — this was a hard lesson we learned after 769 restart loops.

Then add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "basic-memory": {
      "type": "sse",
      "url": "http://localhost:8765/sse"
    },
    "obsidian-vault": {
      "command": "npx",
      "args": ["-y", "@anthropic/obsidian-mcp", "--vault", "/path/to/your/obsidian/vault"]
    }
  }
}
```

### Layer 5: Qdrant Vectors

Seed the vector database:

```bash
# 1. Install dependencies
pip install -r scripts/requirements.txt
# (installs qdrant-client and sentence-transformers)

# 2. Edit scripts/seed-vectors.py — update these constants at the top:
#    QDRANT_PATH  → where to store the vector DB (default: ~/.qdrant-data/my-project)
#    COLLECTION   → name for your collection (default: "my-knowledge")
#    OBSIDIAN_DIR → path to your Obsidian vault
#    MEMORY_DIR   → path to your Claude Code memory files
#                   (find with: ls ~/.claude/projects/*/memory/)

# 3. Run the seeder (first run downloads the embedding model, ~90MB)
python scripts/seed-vectors.py
```

Then add Qdrant to your `.mcp.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "uvx",
      "args": ["mcp-qdrant"],
      "env": {
        "COLLECTION_NAME": "my-knowledge",
        "QDRANT_LOCAL_PATH": "${HOME}/.qdrant-data/my-project",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
      }
    }
  }
}
```

### Layer 6: Memory Files

**No setup needed.** This layer is built into Claude Code.

Claude Code automatically creates memory files in `~/.claude/projects/<project-id>/memory/` when it learns important facts during conversations. The `MEMORY.md` index file loads automatically at the start of every session.

To customize memory behavior, add instructions to your project's `CLAUDE.md` file.

### Layer 7: Session Logs (claude-code-logs)

Install the HTTP log server:

```bash
# 1. Install the Go binary
go install github.com/fabriqaai/claude-code-logs@latest

# 2. Find your Claude Code project ID
ls ~/.claude/projects/
# Use the directory name that matches your project

# 3. Install the systemd service
cp configs/systemd/code-logs.service ~/.config/systemd/user/

# 4. Edit the service file — update the -project flag
#    nano ~/.config/systemd/user/code-logs.service
#    Change "my-project" to your actual project ID from step 2

# 5. Enable and start
systemctl --user daemon-reload
systemctl --user enable --now code-logs

# 6. Verify (should return a 200 OK or JSON response)
curl -s http://localhost:8080/health
```

### Layer 8: Session Watcher

Set up the file watcher that auto-triggers Neo4j reimport:

```bash
# 1. Install inotify-tools
sudo apt install inotify-tools

# 2. Copy and configure the watch script
mkdir -p ~/bin
cp scripts/watch-sessions.sh ~/bin/
chmod +x ~/bin/watch-sessions.sh

# 3. Edit the script — update these variables at the top:
#    PROJECT_ID   → your Claude Code project ID (from Layer 7, step 2)
#    REIMPORT_DIR → path to your context-graph directory (from Layer 3, step 4)
#    nano ~/bin/watch-sessions.sh

# 4. Install the systemd service
cp configs/systemd/session-watcher.service ~/.config/systemd/user/

# 5. Enable and start
systemctl --user daemon-reload
systemctl --user enable --now session-watcher

# 6. Verify
systemctl --user status session-watcher
```

### Periodic Reimport Timer

Install the safety net timer that catches any missed imports:

```bash
# 1. Install both the timer and service
cp configs/systemd/neo4j-reimport.timer ~/.config/systemd/user/
cp configs/systemd/neo4j-reimport.service ~/.config/systemd/user/

# 2. Edit the service — update WorkingDirectory to your context-graph path
#    nano ~/.config/systemd/user/neo4j-reimport.service

# 3. Enable the timer
systemctl --user daemon-reload
systemctl --user enable --now neo4j-reimport.timer

# 4. Verify timer is scheduled
systemctl --user list-timers
```

### Hook Installation

Hooks are the auto-update backbone. Copy them and wire into Claude Code:

```bash
# 1. Create the hooks directory in your project
mkdir -p /path/to/your/project/.claude/hooks
cp configs/hooks/*.sh /path/to/your/project/.claude/hooks/
chmod +x /path/to/your/project/.claude/hooks/*.sh
```

Then create or update `/path/to/your/project/.claude/settings.json`:

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

### Final: Complete `.mcp.json`

Your project's `.mcp.json` should now look something like this (see `configs/mcp-servers.example.json` for the full template):

```json
{
  "mcpServers": {
    "code-review-graph": {
      "command": "code-review-graph",
      "args": ["mcp"]
    },
    "neo4j": {
      "command": "uvx",
      "args": ["mcp-neo4j"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "<your-neo4j-password>",
        "NEO4J_DATABASE": "neo4j"
      }
    },
    "obsidian-vault": {
      "command": "npx",
      "args": ["-y", "@anthropic/obsidian-mcp", "--vault", "/path/to/vault"],
    },
    "basic-memory": {
      "type": "sse",
      "url": "http://localhost:8765/sse"
    },
    "qdrant": {
      "command": "uvx",
      "args": ["mcp-qdrant"],
      "env": {
        "COLLECTION_NAME": "my-knowledge",
        "QDRANT_LOCAL_PATH": "${HOME}/.qdrant-data/my-project",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
      }
    }
  }
}
```

## Verification Checklist

After setup, verify each layer:

```bash
# Layer 1: Graphify
ls graphify-out/graph.json && echo "OK" || echo "MISSING — run: graphify ."

# Layer 2: Code Review Graph
code-review-graph status

# Layer 3: Neo4j
curl -s -u neo4j:$NEO4J_PASSWORD http://localhost:7474/db/neo4j/tx \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"MATCH (n) RETURN count(n)"}]}'

# Layer 4: Obsidian MCP
systemctl --user status basic-memory-sync --no-pager | head -5

# Layer 5: Qdrant
python3 -c "
from pathlib import Path
from qdrant_client import QdrantClient
c = QdrantClient(path=str(Path.home() / '.qdrant-data/my-project'))
print(f'Qdrant: {c.count(\"my-knowledge\").count} vectors')
"

# Layer 6: Memory Files
ls ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null && echo "OK" || echo "No memory files yet — use Claude Code first"

# Layer 7: Session Logs
curl -s http://localhost:8080/health && echo " OK" || echo "FAILED"

# Layer 8: Session Watcher
systemctl --user status session-watcher --no-pager | head -5

# Bonus: All systemd services
systemctl --user list-units 'basic-memory*' 'session-watcher*' 'code-logs*' 'neo4j-reimport*' --no-pager
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| basic-memory restart-loops | Ensure `--transport sse` is in the ExecStart. stdio needs a connected client on stdin — as a daemon, no client exists. |
| Neo4j won't start | Run `docker logs neo4j-knowledge-graph`. Usually a password format issue — NEO4J_AUTH must be `neo4j/<password>`. |
| Session watcher not detecting files | Verify `PROJECT_ID` in the script matches the directory name in `~/.claude/projects/`. |
| Qdrant seed fails | Check paths in `seed-vectors.py`. Both `OBSIDIAN_DIR` and `MEMORY_DIR` must exist. |
| Hooks not firing | Verify `.claude/settings.json` is valid JSON. Check that hook scripts are executable (`chmod +x`). |
| Neo4j reimport fails | Verify the `WorkingDirectory` in the systemd service and that `make import-and-seed` works when run manually. |
| `code-review-graph: command not found` | If installed via pipx, ensure `~/.local/bin` is in your PATH. |
| MCP servers not connecting | Restart Claude Code after editing `.mcp.json`. Claude Code only reads it on startup. |
| `permission denied` on hooks | Claude Code needs execute permission on hook scripts: `chmod +x .claude/hooks/*.sh` |
