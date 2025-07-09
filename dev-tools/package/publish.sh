#!/bin/bash
set -e

ENVIRONMENT=${1:-testpypi}

echo "🚀 Publishing open-hostfactory-plugin to $ENVIRONMENT..."

# Get to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

if [ "$ENVIRONMENT" = "pypi" ]; then
    echo "⚠️  Publishing to PRODUCTION PyPI!"
    echo "   This will make the package publicly available."
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        exit 1
    fi
fi

# Install twine if needed
if ! python -c "import twine" 2>/dev/null; then
    echo "📦 Installing twine..."
    pip install twine
fi

# Build first
echo "🔨 Building package first..."
./dev-tools/package/build.sh

# Check package
echo "🔍 Checking package..."
python -m twine check dist/*

# Publish
echo "📤 Publishing to $ENVIRONMENT..."
if [ "$ENVIRONMENT" = "pypi" ]; then
    python -m twine upload dist/*
else
    python -m twine upload --repository testpypi dist/*
fi

echo "✅ Published to $ENVIRONMENT successfully!"
echo ""
if [ "$ENVIRONMENT" = "testpypi" ]; then
    echo "🧪 Test installation:"
    echo "  pip install --index-url https://test.pypi.org/simple/ open-hostfactory-plugin"
else
    echo "🎉 Production installation:"
    echo "  pip install open-hostfactory-plugin"
fi
