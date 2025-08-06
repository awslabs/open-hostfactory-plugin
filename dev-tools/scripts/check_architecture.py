#!/usr/bin/env python3
"""
Architecture compliance checker.

Validates Clean Architecture, DDD, and CQRS patterns by running
existing architecture tests and checking for violations.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_architecture_tests():
    """Run architecture compliance tests."""
    project_root = Path(__file__).parent.parent.parent
    
    # Run architecture tests
    test_paths = [
        "tests/unit/architecture/",
        "tests/unit/test_architectural_compliance.py"
    ]
    
    failed_tests = []
    
    for test_path in test_paths:
        full_path = project_root / test_path
        if full_path.exists():
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", str(full_path), "-v"],
                    cwd=project_root,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    failed_tests.append((test_path, result.stdout, result.stderr))
                    print(f"FAIL {test_path}")
                    if result.stdout:
                        print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                else:
                    print(f"PASS {test_path}")
                    
            except Exception as e:
                failed_tests.append((test_path, "", str(e)))
                print(f"ERROR {test_path}: {e}")
        else:
            print(f"SKIP {test_path}: Path does not exist")
    
    return len(failed_tests) == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check architecture compliance")
    parser.add_argument(
        "--warn-only", 
        action="store_true", 
        help="Exit with success even if violations found"
    )
    
    args = parser.parse_args()
    
    print("Running architecture compliance checks...")
    
    success = run_architecture_tests()
    
    if success:
        print("Architecture compliance checks passed")
        return 0
    else:
        print("Architecture compliance violations found")
        return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
