#!/usr/bin/env bash
# Post-Tool-Use Hook: Update code review graph after file edits
#
# Triggered by: PostToolUse event on Edit/Write tools
# What it does:
#   1. Runs incremental AST update (--skip-flows for speed)
#   2. Signals that Neo4j should reimport on next cycle
#
# Wire this into .claude/settings.json:
#   "PostToolUse": [{ "matcher": "Edit|Write", "command": ".claude/hooks/post-tool-use.sh" }]

set -euo pipefail

# Update the code review graph (incremental, ~2-5 seconds)
code-review-graph update --skip-flows 2>/dev/null &

# Signal Neo4j that new data is available
# The session watcher or 30-min timer will pick this up
touch /tmp/neo4j-reimport-signal 2>/dev/null || true

wait
