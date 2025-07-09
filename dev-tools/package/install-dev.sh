#!/bin/bash
set -e

echo "🔧 Installing open-hostfactory-plugin in development mode..."

# Get to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

# Ensure we're using the venv's Python explicitly
if [ ! -f ".venv/bin/python" ]; then
    echo "❌ Virtual environment not found at .venv/"
    echo "Please create it first: python3.11 -m venv .venv"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Verify Python version
echo "🐍 Using Python: $(python --version)"
echo "🐍 Python executable: $(which python)"

# Upgrade pip and build tools first
echo "📦 Upgrading pip and build tools..."
python -m pip install --upgrade pip setuptools wheel

# Install in editable mode using the venv's Python explicitly
echo "📦 Installing package in editable mode..."
python -m pip install -e .

# Install development dependencies
echo "📦 Installing development dependencies..."
python -m pip install -r requirements-dev.txt

echo "✅ Development installation complete!"
echo ""
echo "🧪 Testing installation..."

# Test commands
if command -v ohfp &> /dev/null; then
    echo "✅ ohfp command available"
    # Test the command works
    if ohfp --help > /dev/null 2>&1; then
        echo "✅ ohfp --help works"
    else
        echo "⚠️  ohfp command found but --help failed"
    fi
else
    echo "❌ ohfp command not found"
fi

if command -v open-hostfactory-plugin &> /dev/null; then
    echo "✅ open-hostfactory-plugin command available"
    # Test the command works
    if open-hostfactory-plugin --help > /dev/null 2>&1; then
        echo "✅ open-hostfactory-plugin --help works"
    else
        echo "⚠️  open-hostfactory-plugin command found but --help failed"
    fi
else
    echo "❌ open-hostfactory-plugin command not found"
fi

echo ""
echo "🎯 Available commands:"
echo "  ohfp --help                        # Short command"
echo "  open-hostfactory-plugin --help     # Long command"
echo ""
echo "🎯 Example usage:"
echo "  ohfp templates list"
echo "  ohfp machines request basic-template 2"
echo "  open-hostfactory-plugin providers health"
echo ""
echo "🎯 Host Factory integration:"
echo "  USE_LOCAL_DEV=true ./scripts/requestMachines.sh basic-template 2"
