#!/bin/bash

# Get current date and time
DATETIME=$(date +"%Y%m%d_%H%M%S")

# Get the root directory name
ROOT_DIR=$(basename $(pwd))

# Create backup directories
cd ..

BAK_DIR="${ROOT_DIR}.bak"
mkdir -p "$BAK_DIR"

cd "$BAK_DIR"

BACKUP_DIR="backup_$DATETIME"
mkdir "$BACKUP_DIR"

# Copy root folder to backup directory
cp -R ../$ROOT_DIR/* "$BACKUP_DIR"

# Remove .venv and __pycache__ folders
find "$BACKUP_DIR" -type d -name ".venv" -exec rm -rf {} +
find "$BACKUP_DIR" -type d -name "__pycache__" -exec rm -rf {} +

# Remove logs folder
rm -rf "$BACKUP_DIR/logs"

# Remove request database
rm -f "$BACKUP_DIR/data/request_database.json"

# Create the markdown file
MD_FILE="${BACKUP_DIR}/project_structure.md"
touch "$MD_FILE"

# Add directory structure (using tree command)
echo "## Directory Structure" >> "$MD_FILE"
if command -v tree >/dev/null 2>&1; then
  tree "$BACKUP_DIR" >> "$MD_FILE"
else
  echo "Tree command not found.  Using find instead." >> "$MD_FILE"
  find "$BACKUP_DIR" -print | sed 's/\([^/]*\)\/$/|-- \1/g;s/\([^-]\)\/\|/|  /g;s/^/$|-- /' >> "$MD_FILE"
fi

# Add file contents
echo "\n## File Contents" >> "$MD_FILE"

find "$BACKUP_DIR" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.bat" -o -name "*.md" -o -name "*.txt" -o -name "*.json" \) -print0 | while IFS= read -r -d $'\0' file; do
cat << EOF >> "$MD_FILE"

### File: $file:

\`\`\`
$(cat $file)
\`\`\`
EOF
done

# Create tar archive
tar -czf "${BACKUP_DIR}.tar.gz" "$BACKUP_DIR"

echo "Backup created: ${ROOT_DIR}.bak/${BACKUP_DIR}.tar.gz"
echo "Project structure in markdown: ${ROOT_DIR}.bak/$MD_FILE"
echo "Backup folder: ${ROOT_DIR}.bak/$BACKUP_DIR"
