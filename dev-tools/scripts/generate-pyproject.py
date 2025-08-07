#!/usr/bin/env python3
"""Generate pyproject.toml from template using centralized configuration."""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from _version import __version__
    from _package import (
        PACKAGE_NAME,
        PACKAGE_NAME_SHORT,
        REPO_URL,
        DOCS_URL,
        REPO_ISSUES_URL
    )
except ImportError as e:
    print(f"Error importing centralized configuration: {e}")
    print("Make sure src/_version.py and src/_package.py exist")
    sys.exit(1)


def generate_pyproject():
    """Generate pyproject.toml from template."""
    template_path = project_root / "pyproject.toml.template"
    output_path = project_root / "pyproject.toml"
    
    if not template_path.exists():
        print(f"Error: Template file not found: {template_path}")
        sys.exit(1)
    
    # Read template
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Replace placeholders with actual values
    replacements = {
        '{{PACKAGE_NAME}}': PACKAGE_NAME,
        '{{PACKAGE_NAME_SHORT}}': PACKAGE_NAME_SHORT,
        '{{VERSION}}': __version__,
        '{{REPO_URL}}': REPO_URL,
        '{{DOCS_URL}}': DOCS_URL,
        '{{REPO_ISSUES_URL}}': REPO_ISSUES_URL,
    }
    
    generated_content = template_content
    for placeholder, value in replacements.items():
        generated_content = generated_content.replace(placeholder, value)
    
    # Write generated file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(generated_content)
    
    print(f"Generated pyproject.toml from template")
    print(f"Package: {PACKAGE_NAME} v{__version__}")
    print(f"Repository: {REPO_URL}")
    print(f"Entry points: {PACKAGE_NAME_SHORT}, {PACKAGE_NAME}")


if __name__ == "__main__":
    generate_pyproject()
