#!/bin/bash
set -e

# Centralized tool execution script
# Usage: run_tool.sh <tool_name> [args...]
# Tries different execution methods in order of preference

TOOL_NAME="$1"
shift  # Remove tool name from arguments

echo "Running ${TOOL_NAME}..."

# Try different execution methods in order of preference
if command -v uv >/dev/null 2>&1; then
    echo "Using UV-managed ${TOOL_NAME}..."
    uv run "${TOOL_NAME}" "$@"
elif command -v ./.venv/bin/"${TOOL_NAME}" >/dev/null 2>&1; then
    echo "Using venv ${TOOL_NAME}..."
    ./.venv/bin/"${TOOL_NAME}" "$@"
elif command -v "${TOOL_NAME}" >/dev/null 2>&1; then
    echo "Using system ${TOOL_NAME}..."
    "${TOOL_NAME}" "$@"
else
    echo "Using Python module ${TOOL_NAME}..."
    python3 -m "${TOOL_NAME}" "$@"
fi
