#!/usr/bin/env python3
"""Script to fix remaining SIM issues systematically."""

import re
import os
from pathlib import Path

def fix_sim102_in_file(file_path):
    """Fix SIM102 nested if statements in a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern for nested if statements that can be combined
    # This is a simple pattern - more complex cases need manual review
    patterns = [
        # if condition1:\n    if condition2:
        (r'(\s+)if (.+?):\n(\s+)if (.+?):\n(\s+)(.+)', 
         r'\1if \2 and \4:\n\5\6'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed SIM102 in {file_path}")

def fix_sim105_in_file(file_path):
    """Fix SIM105 exception suppression in a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Add contextlib import if not present
    if 'from contextlib import suppress' not in content and 'contextlib.suppress' not in content:
        # Find first import or add at top
        lines = content.split('\n')
        import_line = None
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_line = i
                break
        
        if import_line is not None:
            lines.insert(import_line, 'from contextlib import suppress')
        else:
            lines.insert(0, 'from contextlib import suppress')
        
        content = '\n'.join(lines)
    
    # Pattern for try/except pass blocks
    patterns = [
        # try:\n    statement\nexcept Exception:\n    pass
        (r'(\s+)try:\n(\s+)(.+?)\n\s+except (.+?):\n\s+pass', 
         r'\1with suppress(\4):\n\2\3'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed SIM105 in {file_path}")

def main():
    """Fix SIM issues in the codebase."""
    src_dir = Path('src')
    
    # Get files with SIM issues
    sim102_files = [
        'src/application/services/template_defaults_service.py',
        'src/config/migration.py',
        'src/infrastructure/di/provider_services.py',
        'src/infrastructure/error/decorators.py',
        'src/infrastructure/factories/provider_strategy_factory.py',
        'src/infrastructure/persistence/components/file_manager.py',
        'src/infrastructure/resilience/strategies/circuit_breaker.py',
        'src/infrastructure/scheduler/hostfactory/transformations.py',
        'src/providers/aws/domain/template/aggregate.py',
        'src/providers/aws/strategy/aws_provider_adapter.py',
    ]
    
    sim105_files = [
        'src/infrastructure/di/components/dependency_resolver.py',
        'src/infrastructure/di/handler_discovery.py',
        'src/infrastructure/persistence/components/dynamodb_converter.py',
        'src/providers/aws/infrastructure/template/ami_cache.py',
        'src/providers/aws/registration.py',
        'src/sdk/client.py',
    ]
    
    print("Fixing SIM102 issues...")
    for file_path in sim102_files:
        if os.path.exists(file_path):
            fix_sim102_in_file(file_path)
    
    print("Fixing SIM105 issues...")
    for file_path in sim105_files:
        if os.path.exists(file_path):
            fix_sim105_in_file(file_path)
    
    print("SIM fixes completed. Please review changes manually.")

if __name__ == '__main__':
    main()
