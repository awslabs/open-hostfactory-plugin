#!/bin/bash
# Clean whitespace in blank lines from files

if [ $# -eq 0 ]; then
    # No arguments - clean everything
    find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.txt" -o -name "*.sh" \) -exec sed -i '' 's/^[[:space:]]*$//' {} \;
    echo "Cleaned whitespace in all files"
else
    # Use arguments as find patterns
    for pattern in "$@"; do
        if [ -f "$pattern" ]; then
            # Single file
            sed -i '' 's/^[[:space:]]*$//' "$pattern"
            echo "Cleaned whitespace in $pattern"
        else
            # Pattern for find
            find . -name "$pattern" -type f -exec sed -i '' 's/^[[:space:]]*$//' {} \;
            echo "Cleaned whitespace in files matching $pattern"
        fi
    done
fi
