#!/bin/bash
set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <major|minor|patch|VERSION>"
    echo ""
    echo "Examples:"
    echo "  $0 patch    # 0.1.0 -> 0.1.1"
    echo "  $0 minor    # 0.1.0 -> 0.2.0"
    echo "  $0 major    # 0.1.0 -> 1.0.0"
    echo "  $0 1.2.3    # Set specific version"
    exit 1
fi

BUMP_TYPE=$1

# Get to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

# Get current version
CURRENT_VERSION=$(grep "__version__" src/__init__.py | cut -d'"' -f2)
echo "Current version: $CURRENT_VERSION"

# Calculate new version
if [[ "$BUMP_TYPE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # Specific version provided
    NEW_VERSION=$BUMP_TYPE
else
    # Parse current version
    IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
    MAJOR=${VERSION_PARTS[0]}
    MINOR=${VERSION_PARTS[1]}
    PATCH=${VERSION_PARTS[2]}
    
    case $BUMP_TYPE in
        major)
            MAJOR=$((MAJOR + 1))
            MINOR=0
            PATCH=0
            ;;
        minor)
            MINOR=$((MINOR + 1))
            PATCH=0
            ;;
        patch)
            PATCH=$((PATCH + 1))
            ;;
        *)
            echo "ERROR Invalid bump type: $BUMP_TYPE"
            echo "Use: major, minor, patch, or specific version (e.g., 1.2.3)"
            exit 1
            ;;
    esac
    
    NEW_VERSION="$MAJOR.$MINOR.$PATCH"
fi

echo "New version: $NEW_VERSION"
echo ""
read -p "Update version to $NEW_VERSION? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "ERROR Cancelled"
    exit 1
fi

# Update version in src/__init__.py
echo "📝 Updating src/__init__.py..."
sed -i.bak "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" src/__init__.py
rm src/__init__.py.bak

# Update version in pyproject.toml if it exists
if [ -f pyproject.toml ]; then
    echo "📝 Updating pyproject.toml..."
    sed -i.bak "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
    rm pyproject.toml.bak
fi

echo "SUCCESS Version updated to $NEW_VERSION"
echo ""
echo "🎯 Next steps:"
echo "  • Review changes: git diff"
echo "  • Commit changes: git add -A && git commit -m 'Bump version to $NEW_VERSION'"
echo "  • Create tag: git tag v$NEW_VERSION"
echo "  • Push changes: git push && git push --tags"
echo "  • Build and publish: ./dev-tools/package/build.sh && ./dev-tools/package/publish.sh"
