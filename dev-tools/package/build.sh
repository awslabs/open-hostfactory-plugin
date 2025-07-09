#!/bin/bash
set -e

echo "🔨 Building open-hostfactory-plugin package..."

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

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Install build dependencies if needed
if ! python -c "import build" 2>/dev/null; then
    echo "📦 Installing build dependencies..."
    python -m pip install build
fi

# Build package using the venv's Python
echo "🔨 Building package..."
python -m build --clean

echo "✅ Package built successfully!"
echo "📦 Files created:"
ls -la dist/

echo ""
echo "🎯 Next steps:"
echo "  • Test installation: ./dev-tools/package/test-install.sh"
echo "  • Publish to test PyPI: ./dev-tools/package/publish.sh testpypi"
echo "  • Publish to PyPI: ./dev-tools/package/publish.sh pypi"
