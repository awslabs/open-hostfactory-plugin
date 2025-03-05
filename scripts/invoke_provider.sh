#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="${PARENT_DIR}/src/app.py"

export PYTHONPATH="$PYTHONPATH:$SCRIPT_DIR"

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Python not found" >&2
    exit 1
fi

# Execute the Python script with all arguments passed to this script
$PYTHON_CMD "$PYTHON_SCRIPT" "$@"
