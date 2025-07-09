#!/usr/bin/env python3
"""Import validation script to catch import issues before they break the system.

This script validates that all critical imports work and identifies potential
issues that might be introduced during refactoring.
"""
import sys
import ast
import os
from pathlib import Path
from typing import List, Dict, Set, Tuple
import importlib.util


class ImportValidator:
    """Validates imports across the codebase."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_path = project_root / "src"
        self.critical_files = [
            "run.py",
            "src/bootstrap.py",
            "src/interface/command_handlers.py"
        ]
        
        # Known moved imports after value object decomposition
        self.moved_imports = {
            "MachineStatus": {
                "old": "src.domain.request.value_objects",
                "new": "src.domain.machine.value_objects"
            },
            "BaseCommandHandler": {
                "old": "src.interface.command_handlers",
                "new": "src.infrastructure.handlers"
            }
        }
        
        # Deprecated imports that should fail
        self.deprecated_imports = [
            ("src.domain.request.value_objects", "MachineStatus"),
            ("src.interface.command_handlers", "BaseCommandHandler")
        ]
    
    def extract_imports_from_file(self, file_path: Path) -> List[Tuple[str, List[str]]]:
        """Extract import statements from a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = [alias.name for alias in node.names]
                    imports.append((module, names))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append((alias.name, []))
            
            return imports
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return []
    
    def validate_import(self, module: str, name: str = None) -> Tuple[bool, str]:
        """Validate that an import works."""
        try:
            if name:
                exec(f"from {module} import {name}")
            else:
                exec(f"import {module}")
            return True, "OK"
        except ImportError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    def check_critical_files(self) -> Dict[str, List[str]]:
        """Check imports in critical files."""
        issues = {}
        
        for file_path in self.critical_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            file_issues = []
            imports = self.extract_imports_from_file(full_path)
            
            for module, names in imports:
                if not names:  # Simple import
                    success, error = self.validate_import(module)
                    if not success:
                        file_issues.append(f"import {module}: {error}")
                else:  # from ... import ...
                    for name in names:
                        success, error = self.validate_import(module, name)
                        if not success:
                            file_issues.append(f"from {module} import {name}: {error}")
            
            if file_issues:
                issues[file_path] = file_issues
        
        return issues
    
    def check_deprecated_imports(self) -> List[str]:
        """Check that deprecated imports fail as expected."""
        issues = []
        
        for module, name in self.deprecated_imports:
            success, error = self.validate_import(module, name)
            if success:
                issues.append(f"DEPRECATED import still works: from {module} import {name}")
        
        return issues
    
    def suggest_fixes(self, module: str, name: str) -> str:
        """Suggest fixes for broken imports."""
        if name in self.moved_imports:
            old_module = self.moved_imports[name]["old"]
            new_module = self.moved_imports[name]["new"]
            if module == old_module:
                return f"Try: from {new_module} import {name}"
        
        return "Check if the import path is correct after recent refactoring"
    
    def run_validation(self) -> bool:
        """Run complete import validation."""
        print("🔍 Running Import Validation...")
        print("=" * 50)
        
        # Add project root to Python path
        sys.path.insert(0, str(self.project_root))
        
        all_good = True
        
        # Check critical files
        print("\n📋 Checking Critical Files:")
        critical_issues = self.check_critical_files()
        
        if critical_issues:
            all_good = False
            for file_path, issues in critical_issues.items():
                print(f"\n❌ {file_path}:")
                for issue in issues:
                    print(f"  • {issue}")
                    
                    # Try to suggest fixes
                    if "cannot import name" in issue:
                        parts = issue.split("'")
                        if len(parts) >= 2:
                            name = parts[1]
                            suggestion = self.suggest_fixes("", name)
                            print(f"    💡 {suggestion}")
        else:
            print("✅ All critical file imports working")
        
        # Check deprecated imports
        print("\n📋 Checking Deprecated Imports:")
        deprecated_issues = self.check_deprecated_imports()
        
        if deprecated_issues:
            all_good = False
            for issue in deprecated_issues:
                print(f"❌ {issue}")
        else:
            print("✅ All deprecated imports properly failing")
        
        # Summary
        print("\n" + "=" * 50)
        if all_good:
            print("🎉 All import validations passed!")
            return True
        else:
            print("❌ Import validation failed - see issues above")
            return False


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    validator = ImportValidator(project_root)
    
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
