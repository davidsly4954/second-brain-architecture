# Recommended Setup

Hardware requirements, why 24/7 operation matters, and how to recover after a reboot.

---

## Minimum Hardware

The knowledge graph layers are lightweight individually, but they add up. Here's what each layer needs:

| Component | RAM | Disk | CPU | Notes |
|-----------|-----|------|-----|-------|
| **Neo4j** (Docker) | 2 GB | 500 MB–2 GB | 1 core | Heap grows with session count. Default 2G limit is fine for most projects. |
| **Qdrant** (local) | 200–500 MB | 100–500 MB | Minimal | Scales with vector count. A few hundred docs stays under 500 MB total. |
| **basic-memory** (SSE daemon) | 100–200 MB | Negligible | Minimal | Indexes your Obsidian vault. Memory scales with vault size. |
| **claude-code-logs** (Go binary) | 50–100 MB | Negligible | Minimal | HTTP server serving JSONL files. Very efficient. |
| **Embedding model** (seed time) | 500 MB–1 GB | ~90 MB | 1+ cores | `all-MiniLM-L6-v2` loads during seeding only, not at runtime. GPU optional. |
| **Session watcher** (inotifywait) | ~5 MB | Negligible | Negligible | Kernel-level file watching. Nearly zero overhead. |
| **Docker engine** | 300–500 MB | 1–3 GB | Shared | Base Docker overhead. Already installed on most dev machines. |

### Recommended Minimums

| Tier | RAM | Disk | CPU | Good For |
|------|-----|------|-----|----------|
| **Minimum viable** | 8 GB | 20 GB free | 2 cores | One project, small vault, occasional use |
| **Comfortable** | 16 GB | 50 GB free | 4 cores | Multiple projects, active development, large Obsidian vault |
| **Power user** | 32+ GB | 100+ GB free | 8+ cores | Many projects, large session history, fast embedding |

### What You Can Skip

Not every layer needs dedicated hardware:

- **No GPU required.** The embedding model (`all-MiniLM-L6-v2`) runs fine on CPU. Seeding a few hundred documents takes ~30 seconds on a modern laptop.
- **No SSD required** (but strongly recommended). Neo4j and Qdrant benefit from fast random reads. On an HDD, imports and queries will be noticeably slower.
- **No server required.** Everything runs on a standard Linux laptop or desktop. A dedicated server is nice but not necessary.

---

## Why 24/7 Operation Is Better

The knowledge graph is designed around **continuous, automatic updates**. Here's what happens when the machine is running vs. powered off:

### When Running

- **Session watcher** (Layer 8) detects new Claude Code sessions within seconds and triggers Neo4j reimport automatically.
- **30-minute timer** catches any sessions the watcher missed — a safety net that only works if the timer is running.
- **basic-memory daemon** keeps your Obsidian vault index current in real-time. Any note you edit is searchable via MCP within seconds.
- **Claude Code hooks** fire on every file edit, keeping the code review graph (Layer 2) perfectly in sync with your codebase.

### When Powered Off

- Session JSONL files accumulate without being imported into Neo4j. Cross-session queries return stale data.
- Obsidian vault changes aren't indexed. MCP queries miss recent notes.
- The code review graph falls behind. Claude Code loses awareness of recent structural changes.
- No hooks fire, so no automatic updates happen to any layer.

### The Cold Start Problem

When you power on after downtime, the first Claude Code session starts with stale knowledge across multiple layers. The system catches up eventually (the timer fires, the watcher processes backlog), but that first session operates on outdated context. With 24/7 operation, every session starts with current data.

### Recommended Approach

| Scenario | Recommendation |
|----------|---------------|
| Dedicated dev machine (desktop) | Leave it running 24/7. Set display to sleep, not the machine. |
| Laptop (mobile use) | Run when docked. The system recovers gracefully on boot (see below). |
| Shared/cloud server | Ideal — always-on by nature. Run Docker + systemd services there, develop locally. |
| Low-power concerns | The idle load is minimal (~2.5 GB RAM, negligible CPU). Modern hardware draws 10–30W at idle. |

---

## Reboot Recovery

After a reboot, most services restart automatically **if you enabled them with `systemctl --user enable`**. Here's exactly what happens and what might need manual attention.

### What Auto-Recovers (No Action Needed)

These services are configured with `systemctl --user enable`, which means systemd starts them automatically on login:

| Service | Starts On | Verification |
|---------|-----------|-------------|
| `basic-memory-sync` | User login | `systemctl --user status basic-memory-sync` |
| `session-watcher` | User login | `systemctl --user status session-watcher` |
| `code-logs` | User login | `curl -s http://localhost:8080/health` |
| `neo4j-reimport.timer` | User login | `systemctl --user list-timers` |

**Important:** systemd user services start on **login**, not on boot. If your machine boots but no one logs in (e.g., headless server), you need lingering enabled:

```bash
# Enable lingering so user services start at boot, not login
sudo loginctl enable-linger $USER
```

### What Needs a Manual Restart

**Docker containers** — If you used `restart: unless-stopped` in your docker-compose.yml (the default in our template), Docker restarts Neo4j automatically on boot. Verify:

```bash
# Check Docker auto-starts on boot
systemctl is-enabled docker
# Should output: enabled

# Check Neo4j container is running
docker ps --filter name=neo4j-knowledge-graph
# Should show the container with status "Up"

# If the container didn't start:
docker compose -f /path/to/configs/docker-compose.yml up -d
```

### Post-Reboot Verification Script

Run this after any reboot to confirm everything is healthy:

```bash
#!/usr/bin/env bash
# Save as ~/bin/verify-knowledge-graph.sh
# Run after reboot to verify all layers are operational

echo "=== Knowledge Graph Post-Reboot Check ==="
echo ""

# Docker / Neo4j
echo -n "Neo4j (Docker):          "
if docker ps --filter name=neo4j-knowledge-graph --format '{{.Status}}' 2>/dev/null | grep -q "Up"; then
    echo "OK ($(docker ps --filter name=neo4j-knowledge-graph --format '{{.Status}}'))"
else
    echo "DOWN — run: docker compose -f /path/to/configs/docker-compose.yml up -d"
fi

# Neo4j connectivity
echo -n "Neo4j (bolt):            "
if curl -sf http://localhost:7474 >/dev/null 2>&1; then
    echo "OK"
else
    echo "NOT RESPONDING — check: docker logs neo4j-knowledge-graph"
fi

# basic-memory
echo -n "basic-memory (SSE):      "
STATUS=$(systemctl --user is-active basic-memory-sync 2>/dev/null)
if [ "$STATUS" = "active" ]; then
    echo "OK"
else
    echo "$STATUS — run: systemctl --user start basic-memory-sync"
fi

# session watcher
echo -n "session-watcher:         "
STATUS=$(systemctl --user is-active session-watcher 2>/dev/null)
if [ "$STATUS" = "active" ]; then
    echo "OK"
else
    echo "$STATUS — run: systemctl --user start session-watcher"
fi

# code-logs
echo -n "claude-code-logs:        "
STATUS=$(systemctl --user is-active code-logs 2>/dev/null)
if [ "$STATUS" = "active" ]; then
    echo "OK"
else
    echo "$STATUS — run: systemctl --user start code-logs"
fi

# reimport timer
echo -n "neo4j-reimport.timer:    "
STATUS=$(systemctl --user is-active neo4j-reimport.timer 2>/dev/null)
if [ "$STATUS" = "active" ]; then
    echo "OK"
else
    echo "$STATUS — run: systemctl --user enable --now neo4j-reimport.timer"
fi

# Environment variables
echo ""
echo -n "NEO4J_PASSWORD:          "
if [ -n "$NEO4J_PASSWORD" ]; then
    echo "SET"
else
    echo "MISSING — check ~/.bashrc"
fi

echo -n "OBSIDIAN_VAULT_PATH:     "
if [ -n "$OBSIDIAN_VAULT_PATH" ]; then
    echo "SET ($OBSIDIAN_VAULT_PATH)"
else
    echo "MISSING — check ~/.bashrc (optional if not using Layer 4)"
fi

echo ""
echo "=== Check Complete ==="
```

### Environment Variables

Environment variables set in `~/.bashrc` (or `~/.zshrc`) survive reboots automatically — they reload on every new shell. The setup guide instructs you to persist these:

- `NEO4J_PASSWORD` — Required for Neo4j connections
- `OBSIDIAN_VAULT_PATH` — Required for Layer 4 (Obsidian MCP)

If these are missing after reboot, they were likely set with `export` in a terminal but never added to `~/.bashrc`. Re-add them:

```bash
echo 'export NEO4J_PASSWORD="your-password-here"' >> ~/.bashrc
echo 'export OBSIDIAN_VAULT_PATH="/path/to/your/vault"' >> ~/.bashrc
source ~/.bashrc
```

### Recovery Time

After a clean reboot with everything configured correctly:

| Event | Time | What Happens |
|-------|------|-------------|
| Boot | 0s | Docker starts, Neo4j container begins starting |
| +10–30s | Neo4j ready | Bolt endpoint accepts connections |
| Login | +0s | systemd user services start (or immediately if lingering enabled) |
| +2–5s | All daemons ready | basic-memory, session-watcher, code-logs, reimport timer |
| +0–30min | First timer fire | Neo4j reimport catches up on any missed sessions |
| +0s (manual) | Qdrant re-seed | Only needed if new Obsidian notes or memory files were added while offline |

**Total recovery time: under 1 minute for automatic services, up to 30 minutes for the first Neo4j reimport cycle.**

### Quick Recovery Commands

If something didn't auto-start, these commands fix it:

```bash
# Start everything in one shot
docker compose -f /path/to/configs/docker-compose.yml up -d
systemctl --user start basic-memory-sync session-watcher code-logs
systemctl --user enable --now neo4j-reimport.timer

# Trigger an immediate Neo4j reimport (don't wait for the timer)
cd /path/to/context-graph && make import-and-seed

# Re-seed vectors (only if you added content while offline)
python scripts/seed-vectors.py
```

---

## Operating System

**Linux is required.** The system depends on:

- **systemd user services** — for daemon management and timers (not available on macOS or Windows natively)
- **inotifywait** — Linux kernel's inotify API for file watching (no macOS equivalent with the same API)
- **Docker** — available on all platforms, but the systemd integration is Linux-only

macOS and Windows users can adapt the system (launchd on macOS, Task Scheduler on Windows), but the provided configs and scripts are Linux-specific.

**Tested on:** Ubuntu 22.04+, Debian 12+, Kali Linux 2024+, Arch Linux. Should work on any systemd-based distribution.
