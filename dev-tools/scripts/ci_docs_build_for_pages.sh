#!/bin/bash
set -e

# CI Documentation Build for GitHub Pages Script
# Builds documentation with mike but deploys locally (no push)
# Output goes to docs/site for GitHub Pages artifact upload

echo "Building documentation for GitHub Pages deployment..."

cd docs

# Clean any existing site directory
rm -rf site

# Try different mike installation methods in order of preference
if command -v ../.venv/bin/mike >/dev/null 2>&1; then
    echo "Using venv mike..."
    ../.venv/bin/mike deploy --update-aliases latest
    ../.venv/bin/mike set-default latest
elif command -v mike >/dev/null 2>&1; then
    echo "Using system mike..."
    mike deploy --update-aliases latest
    mike set-default latest
else
    echo "Using Python module mike..."
    python3 -m mike deploy --update-aliases latest
    python3 -m mike set-default latest
fi

echo "Verifying site directory exists..."
if [ -d "site" ]; then
    echo "Site directory created successfully"
    echo "Site contents:"
    ls -la site/ | head -10
else
    echo "Error: site directory not found"
    exit 1
fi

echo "Documentation built successfully for GitHub Pages"
