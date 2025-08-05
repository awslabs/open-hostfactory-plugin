#!/usr/bin/env python3
"""
Comprehensive CI Testing Script

This script runs the same checks that are executed in the CI pipeline,
allowing developers to catch issues locally before pushing.

Matches the checks in .github/workflows/ci.yml exactly.

Usage:
    python dev-tools/scripts/ci_check.py [--quick] [--fix] [--verbose]

Options:
    --quick     Run only fast checks (skip slow tests)
    --fix       Attempt to fix formatting issues automatically
    --verbose   Show detailed output from all commands
"""

import argparse
import configparser
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class CIChecker:
    """Comprehensive CI testing that matches GitHub Actions workflow."""
    
    def __init__(self, verbose: bool = False, fix: bool = False):
        self.verbose = verbose
        self.fix = fix
        self.failed_checks = []
        self.project_root = Path(__file__).parent.parent.parent
        
    def run_command(self, cmd: List[str], description: str, allow_failure: bool = False) -> bool:
        """Run a command and return success status."""
        if self.verbose:
            print(f"Running: {' '.join(cmd)}")
            
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=not self.verbose,
                text=True,
                check=True
            )
            print(f"PASS: {description}")
            return True
        except subprocess.CalledProcessError as e:
            if allow_failure:
                print(f"WARN: {description} (allowed to fail)")
                if self.verbose and e.stdout:
                    print(f"Output: {e.stdout}")
                if self.verbose and e.stderr:
                    print(f"Error: {e.stderr}")
                return True
            else:
                print(f"FAIL: {description}")
                if e.stdout:
                    print(f"Output: {e.stdout}")
                if e.stderr:
                    print(f"Error: {e.stderr}")
                self.failed_checks.append(description)
                return False
        except FileNotFoundError:
            print(f"FAIL: {description} (command not found)")
            self.failed_checks.append(f"{description} (command not found)")
            return False
    
    def check_mypy_config(self) -> bool:
        """Check mypy.ini configuration for common issues."""
        print("Checking mypy.ini configuration...")
        
        mypy_ini = self.project_root / "mypy.ini"
        if not mypy_ini.exists():
            print("FAIL: mypy.ini not found")
            self.failed_checks.append("mypy.ini not found")
            return False
            
        try:
            config = configparser.ConfigParser()
            config.read(mypy_ini)
            
            # Check Python version
            if 'mypy' in config:
                python_version = config['mypy'].get('python_version', 'not found')
                try:
                    # Parse version as major.minor
                    version_parts = python_version.split('.')
                    if len(version_parts) >= 2:
                        major = int(version_parts[0])
                        minor = int(version_parts[1])
                        version_tuple = (major, minor)
                        
                        if version_tuple < (3, 9):
                            print(f"FAIL: Python version {python_version} is too old (need 3.9+)")
                            self.failed_checks.append(f"Python version {python_version} too old")
                            return False
                    else:
                        raise ValueError("Invalid version format")
                except (ValueError, IndexError):
                    print(f"FAIL: Invalid Python version format: {python_version}")
                    self.failed_checks.append(f"Invalid Python version format: {python_version}")
                    return False
                    
            # Check for per-module flag issues
            for section_name in config.sections():
                if section_name.startswith('mypy-') and not section_name.startswith('mypy-tests'):
                    section = config[section_name]
                    # Only certain flags are allowed in per-module sections
                    allowed_flags = {'ignore_missing_imports', 'follow_imports', 'disallow_untyped_defs'}
                    for key in section.keys():
                        if key not in allowed_flags:
                            print(f"FAIL: Invalid per-module flag in {section_name}: {key}")
                            self.failed_checks.append(f"Invalid per-module flag: {section_name}.{key}")
                            return False
                            
            print("PASS: mypy.ini configuration")
            return True
            
        except Exception as e:
            print(f"FAIL: mypy.ini configuration error: {e}")
            self.failed_checks.append(f"mypy.ini error: {e}")
            return False
    
    def check_python_version_consistency(self) -> bool:
        """Check Python version consistency across configuration files."""
        print("Checking Python version consistency...")
        
        # Check pyproject.toml
        pyproject_toml = self.project_root / "pyproject.toml"
        if pyproject_toml.exists():
            content = pyproject_toml.read_text()
            if 'python_version = "3.8"' in content:
                print("FAIL: pyproject.toml still has Python 3.8 (need 3.11+)")
                self.failed_checks.append("pyproject.toml Python version too old")
                return False
                
        print("PASS: Python version consistency")
        return True
    
    def check_syntax_errors(self) -> bool:
        """Check for Python syntax errors in key files."""
        print("Checking Python syntax...")
        
        # Files that commonly have syntax issues
        problem_files = [
            "src/api/handlers/get_available_templates_handler.py",
            "src/api/handlers/request_machines_handler.py",
            "src/api/routers/templates.py"
        ]
        
        all_passed = True
        for file_path in problem_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                if not self.run_command(
                    [sys.executable, "-m", "py_compile", str(full_path)],
                    f"Python syntax check: {file_path}"
                ):
                    all_passed = False
                    
        return all_passed
    
    def run_formatting_checks(self) -> bool:
        """Run code formatting checks (Black, isort)."""
        print("\n=== Code Formatting Checks ===")
        
        all_passed = True
        
        # Black formatting check
        black_cmd = [sys.executable, "-m", "black", "--check", "src/", "tests/"]
        if self.fix:
            black_cmd = [sys.executable, "-m", "black", "src/", "tests/"]
            
        if not self.run_command(black_cmd, "Black code formatting"):
            all_passed = False
            
        # isort import sorting check
        isort_cmd = [sys.executable, "-m", "isort", "--check-only", "src/", "tests/"]
        if self.fix:
            isort_cmd = [sys.executable, "-m", "isort", "src/", "tests/"]
            
        if not self.run_command(isort_cmd, "isort import sorting"):
            all_passed = False
            
        return all_passed
    
    def run_linting_checks(self) -> bool:
        """Run linting checks (flake8, mypy, pylint)."""
        print("\n=== Linting Checks ===")
        
        all_passed = True
        
        # flake8 style guide
        if not self.run_command(
            [sys.executable, "-m", "flake8", "src/", "tests/"],
            "flake8 style guide"
        ):
            all_passed = False
            
        # mypy type checking
        if not self.run_command(
            [sys.executable, "-m", "mypy", "src/"],
            "mypy type checking"
        ):
            all_passed = False
            
        # pylint code analysis (allowed to fail)
        self.run_command(
            [sys.executable, "-m", "pylint", "src/"],
            "pylint code analysis",
            allow_failure=True
        )
        
        return all_passed
    
    def run_complexity_analysis(self) -> bool:
        """Run complexity analysis (allowed to fail)."""
        print("\n=== Complexity Analysis ===")
        
        # Radon complexity analysis (allowed to fail)
        self.run_command(
            [sys.executable, "-m", "radon", "cc", "src/", "--min", "B", "--show-complexity"],
            "radon cyclomatic complexity",
            allow_failure=True
        )
        
        self.run_command(
            [sys.executable, "-m", "radon", "mi", "src/", "--min", "B"],
            "radon maintainability index",
            allow_failure=True
        )
        
        return True
    
    def run_security_checks(self) -> bool:
        """Run security checks (bandit, safety)."""
        print("\n=== Security Checks ===")
        
        # bandit security linter (allowed to fail)
        self.run_command(
            [sys.executable, "-m", "bandit", "-r", "src/", "-f", "json", "-o", "bandit-report.json"],
            "bandit security linter",
            allow_failure=True
        )
        
        self.run_command(
            [sys.executable, "-m", "bandit", "-r", "src/", "-f", "txt"],
            "bandit security linter (text output)",
            allow_failure=True
        )
        
        # safety dependency vulnerability check (allowed to fail)
        self.run_command(
            [sys.executable, "-m", "safety", "check"],
            "safety dependency vulnerability check",
            allow_failure=True
        )
        
        return True
    
    def run_tests(self, quick: bool = False) -> bool:
        """Run test suite."""
        print("\n=== Test Suite ===")
        
        if quick:
            return self.run_command(
                [sys.executable, "dev-tools/testing/run_tests.py", "--unit", "--fast"],
                "quick test suite"
            )
        else:
            return self.run_command(
                [sys.executable, "dev-tools/testing/run_tests.py"],
                "full test suite"
            )
    
    def run_all_checks(self, quick: bool = False) -> bool:
        """Run all CI checks."""
        print("=== Comprehensive CI Testing ===")
        print("Running the same checks as GitHub Actions CI pipeline...")
        print()
        
        # Configuration checks
        config_passed = (
            self.check_mypy_config() and
            self.check_python_version_consistency() and
            self.check_syntax_errors()
        )
        
        if not config_passed:
            print("\nConfiguration checks failed. Fix these before running other checks.")
            return False
        
        # Code quality checks
        formatting_passed = self.run_formatting_checks()
        linting_passed = self.run_linting_checks()
        
        # Optional checks (don't fail CI)
        self.run_complexity_analysis()
        self.run_security_checks()
        
        # Tests
        if not quick:
            tests_passed = self.run_tests(quick=quick)
        else:
            tests_passed = True  # Skip tests in quick mode
        
        # Summary
        print("\n=== CI Check Summary ===")
        if self.failed_checks:
            print("FAILED CHECKS:")
            for check in self.failed_checks:
                print(f"  - {check}")
            print()
            print("Fix these issues before pushing to avoid CI failures.")
            return False
        else:
            print("All critical CI checks passed!")
            if self.fix:
                print("Formatting issues have been automatically fixed.")
            return True


def main():
    parser = argparse.ArgumentParser(description="Run comprehensive CI checks locally")
    parser.add_argument("--quick", action="store_true", help="Run only fast checks")
    parser.add_argument("--fix", action="store_true", help="Fix formatting issues automatically")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    
    args = parser.parse_args()
    
    checker = CIChecker(verbose=args.verbose, fix=args.fix)
    success = checker.run_all_checks(quick=args.quick)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
