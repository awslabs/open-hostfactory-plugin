#!/usr/bin/env python3
"""Clean whitespace in blank lines from files."""

import argparse
import re
import sys
from pathlib import Path
from typing import List

def clean_whitespace_in_file(file_path: Path) -> bool:
    """Clean whitespace in blank lines from a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace lines with only whitespace with empty lines
        cleaned_content = re.sub(r'^[ \t]+$', '', content, flags=re.MULTILINE)
        
        if content != cleaned_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def find_files(paths: List[str], extensions: List[str]) -> List[Path]:
    """Find files matching the given extensions in the specified paths."""
    files = []
    
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for ext in extensions:
                files.extend(path.rglob(f"*.{ext}"))
    
    return files

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Clean whitespace in blank lines from files")
    parser.add_argument('paths', nargs='*', default=['src', 'tests'], 
                       help='Paths to process (default: src tests)')
    parser.add_argument('--extensions', '-e', nargs='*', 
                       default=['py', 'md', 'yml', 'yaml', 'json', 'txt', 'sh'],
                       help='File extensions to process (default: py md yml yaml json txt sh)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without making changes')
    
    args = parser.parse_args()
    
    files = find_files(args.paths, args.extensions)
    
    if not files:
        print("No files found to process")
        return 0
    
    changed_files = []
    
    for file_path in files:
        if args.dry_run:
            print(f"Would process: {file_path}")
        else:
            if clean_whitespace_in_file(file_path):
                changed_files.append(file_path)
    
    if not args.dry_run:
        if changed_files:
            print(f"Cleaned whitespace in {len(changed_files)} files:")
            for file_path in changed_files:
                print(f"  {file_path}")
        else:
            print("No files needed whitespace cleaning")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
