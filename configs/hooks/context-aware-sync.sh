#!/usr/bin/env bash
# Context-Aware Sync Hook: Prompt knowledge dump before compaction
#
# Triggered by: PreToolUse event on ALL tools
# What it does:
#   1. Checks the current session JSONL file size
#   2. If approaching the compaction threshold (~3MB / ~200K tokens),
#      outputs a reminder to dump important knowledge to memory files
#   3. Only fires once per session (uses a flag file)
#
# Wire this into .claude/settings.json:
#   "PreToolUse": [{ "matcher": ".*", "command": ".claude/hooks/context-aware-sync.sh" }]

# Compaction threshold in bytes (~3MB ≈ ~200K tokens)
THRESHOLD=3000000

# Find the current session JSONL file
# Claude Code stores sessions in ~/.claude/projects/<encoded-project-name>/
PROJECT_DIR="$HOME/.claude/projects"
SESSION_FILE=$(find "$PROJECT_DIR" -name "*.jsonl" -newer /tmp/ctx-sync-session.flag 2>/dev/null | head -1)

# Skip if no session file found or flag already set
FLAG="/tmp/ctx-sync-$(date +%Y%m%d).flag"
[ -f "$FLAG" ] && exit 0
[ -z "${SESSION_FILE:-}" ] && exit 0

# Check file size
SIZE=$(stat -c%s "$SESSION_FILE" 2>/dev/null || echo 0)

if [ "$SIZE" -gt "$THRESHOLD" ]; then
    touch "$FLAG"
    echo "Context approaching compaction threshold (${SIZE} bytes)."
    echo "Consider dumping important knowledge to memory files before context is compressed."
fi
