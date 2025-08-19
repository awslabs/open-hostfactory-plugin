#!/bin/bash
set -e

# Centralized tool execution script with environment setup
# Usage: run_tool.sh <tool_name> [args...]
# Handles environment setup and tries different execution methods

TOOL_NAME="$1"
shift  # Remove tool name from arguments

setup_environment() {
    # UV-first approach (fastest and most reliable)
    if command -v uv >/dev/null 2>&1; then
        # Check if we're in a UV project (current dir or parent dirs)
        current_dir="$PWD"
        while [ "$current_dir" != "/" ]; do
            if [ -f "$current_dir/pyproject.toml" ] || [ -f "$current_dir/uv.lock" ]; then
                echo "Using UV-managed environment..."
                return 0
            fi
            current_dir=$(dirname "$current_dir")
        done
    fi

    # Fallback to .venv if it exists (check parent dirs too)
    current_dir="$PWD"
    while [ "$current_dir" != "/" ]; do
        if [ -f "$current_dir/.venv/bin/activate" ]; then
            echo "Using existing .venv environment..."
            # shellcheck disable=SC1091
            source "$current_dir/.venv/bin/activate"
            return 0
        fi
        current_dir=$(dirname "$current_dir")
    done

    # Use system environment as last resort
    echo "Using system environment..."
}

run_tool() {
    setup_environment

    echo "Running ${TOOL_NAME}..."

    # Find project root for UV
    project_root="$PWD"
    while [ "$project_root" != "/" ]; do
        if [ -f "$project_root/pyproject.toml" ] || [ -f "$project_root/uv.lock" ]; then
            break
        fi
        project_root=$(dirname "$project_root")
    done

    # Try different execution methods in order of preference
    if command -v uv >/dev/null 2>&1 && [ -f "$project_root/pyproject.toml" ]; then
        echo "Executing with UV..."
        cd "$project_root" && uv run "${TOOL_NAME}" "$@"
    elif [ -f ".venv/bin/${TOOL_NAME}" ]; then
        echo "Executing with venv..."
        .venv/bin/"${TOOL_NAME}" "$@"
    elif command -v "${TOOL_NAME}" >/dev/null 2>&1; then
        echo "Executing with system..."
        "${TOOL_NAME}" "$@"
    else
        echo "Executing as Python module..."
        if command -v uv >/dev/null 2>&1 && [ -f "$project_root/pyproject.toml" ]; then
            cd "$project_root" && uv run python -m "${TOOL_NAME}" "$@"
        else
            python3 -m "${TOOL_NAME}" "$@"
        fi
    fi
}

# Execute the tool
run_tool "$@"
