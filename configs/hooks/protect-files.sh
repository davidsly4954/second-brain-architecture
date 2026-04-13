#!/usr/bin/env bash
# Protect Files Hook: Block writes to sensitive files
#
# Triggered by: PreToolUse event on Edit/Write tools
# What it does:
#   1. Checks if the target file matches a blocklist pattern
#   2. If matched, exits with non-zero status to block the edit
#   3. Protects: .env files, secrets directories, settings files
#
# Wire this into .claude/settings.json:
#   "PreToolUse": [{ "matcher": "Edit|Write", "command": ".claude/hooks/protect-files.sh" }]

# The tool input is passed via environment or stdin
# $CLAUDE_TOOL_INPUT contains the JSON with file_path
FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Patterns to block
BLOCKED_PATTERNS=(
    "\.env"
    "\.env\."
    "secrets/"
    "credentials/"
    "\.claude/settings\.json"
    "\.ssh/"
    "\.aws/"
    "\.gnupg/"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$FILE_PATH" | grep -qE "$pattern"; then
        echo "BLOCKED: Cannot edit files matching pattern '$pattern'"
        echo "This file is protected by the second brain safety hook."
        exit 1
    fi
done

exit 0
