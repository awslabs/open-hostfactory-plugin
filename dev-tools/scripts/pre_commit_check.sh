#!/bin/bash
"""Pre-commit validation script - simulates .pre-commit-config.yaml hooks using Makefile targets."""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

echo "Running pre-commit checks (simulating .pre-commit-config.yaml via Makefile)..."

# Function to run Makefile target and report result
run_make_target() {
    local name="$1"
    local target="$2"
    
    echo -n "Running $name... "
    if make "$target" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Run: make $target"
        return 1
    fi
}

# Track failures
FAILED=0

echo "Simulating pre-commit hooks from .pre-commit-config.yaml via Makefile:"
echo ""

# 1. Quality Check
if ! run_make_target "quality-check" "quality-check"; then
    FAILED=1
fi

# 2. Validate Imports
if ! run_make_target "validate-imports" "ci-imports"; then
    FAILED=1
fi

# 3. Validate CQRS
if ! run_make_target "validate-cqrs" "ci-arch-cqrs"; then
    FAILED=1
fi

# 4. Check Architecture
if ! run_make_target "check-architecture" "ci-arch-clean"; then
    FAILED=1
fi

# 5. Security Scan
if ! run_make_target "security-scan" "security-scan"; then
    FAILED=1
fi

# 6. Validate Workflows
if ! run_make_target "validate-workflows" "validate-workflows"; then
    FAILED=1
fi

# Summary
echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}SUCCESS: All pre-commit checks passed${NC}"
    echo "Ready to commit!"
    exit 0
else
    echo -e "${RED}FAILED: Some pre-commit checks failed${NC}"
    echo "Please fix the issues above before committing."
    echo ""
    echo "Quick fixes:"
    echo "  make format  # Fix formatting issues"
    echo "  make lint    # Run all linting checks"
    echo "  make test    # Run tests"
    exit 1
fi
