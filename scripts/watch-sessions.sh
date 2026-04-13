#!/usr/bin/env bash
# Session Watcher: Detect new Claude Code sessions and trigger Neo4j reimport
#
# Uses inotifywait to watch for JSONL file changes in the Claude Code
# projects directory. When a session file is created or modified, it
# waits for a debounce period (to batch rapid writes), then triggers
# the Neo4j reimport pipeline.
#
# Install: sudo apt install inotify-tools
# Run as systemd service: see configs/systemd/session-watcher.service

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────
# Update PROJECT_ID to match your Claude Code project directory name.
# Find it with: ls ~/.claude/projects/

PROJECT_ID="my-project"
WATCH_DIR="$HOME/.claude/projects/$PROJECT_ID"
DEBOUNCE_SECONDS=30
LOCK_FILE="/tmp/neo4j-reimport.lock"
REIMPORT_DIR="$HOME/second-brain/context-graph"

# ── Functions ──────────────────────────────────────────────────

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] session-watcher: $*"
}

do_reimport() {
    # Prevent concurrent reimports
    if [ -f "$LOCK_FILE" ]; then
        log "Reimport already in progress, skipping"
        return
    fi

    touch "$LOCK_FILE"
    trap 'rm -f "$LOCK_FILE"' EXIT

    log "Triggering Neo4j reimport..."
    if cd "$REIMPORT_DIR" && make import-and-seed >> /tmp/neo4j-reimport.log 2>&1; then
        log "Reimport complete"
    else
        log "Reimport failed (check /tmp/neo4j-reimport.log)"
    fi

    rm -f "$LOCK_FILE"
    trap - EXIT
}

# ── Main Loop ──────────────────────────────────────────────────

if ! command -v inotifywait &>/dev/null; then
    echo "Error: inotifywait not found. Install with: sudo apt install inotify-tools"
    exit 1
fi

if [ ! -d "$WATCH_DIR" ]; then
    echo "Error: Watch directory not found: $WATCH_DIR"
    echo "Check your PROJECT_ID setting."
    exit 1
fi

log "Watching $WATCH_DIR for JSONL changes (debounce: ${DEBOUNCE_SECONDS}s)"

# Watch for close_write events on .jsonl files
inotifywait -m -e close_write --include '\.jsonl$' "$WATCH_DIR" |
while read -r directory event filename; do
    log "Detected change: $filename ($event)"

    # Debounce: wait before reimporting to batch rapid writes
    sleep "$DEBOUNCE_SECONDS"

    do_reimport
done
