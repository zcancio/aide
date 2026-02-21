#!/usr/bin/env bash
# local-checks.sh — Mirrors CI. Exit on first failure.
# Usage: bash .claude/skills/spec-to-merge/scripts/local-checks.sh [--fix]
set -euo pipefail

FIX_MODE=false
if [[ "${1:-}" == "--fix" ]]; then
  FIX_MODE=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; echo -e "${RED}HALT: $2${NC}"; exit 1; }
skip() { echo -e "  ${YELLOW}○${NC} $1 (skipped — $2)"; }

echo "Running local checks..."
echo ""

# 1. Lint
if [ -d "backend/" ]; then
  if $FIX_MODE; then
    ruff check backend/ --fix 2>/dev/null && pass "ruff check (auto-fixed)" || fail "ruff check" "Lint errors remain after auto-fix"
  else
    ruff check backend/ 2>/dev/null && pass "ruff check" || fail "ruff check" "Run with --fix or: ruff check backend/ --fix"
  fi
else
  skip "ruff check" "no backend/ directory"
fi

# 2. Format
if [ -d "backend/" ]; then
  if $FIX_MODE; then
    ruff format backend/ 2>/dev/null && pass "ruff format (applied)" || fail "ruff format" "Format failed"
  else
    ruff format --check backend/ 2>/dev/null && pass "ruff format" || fail "ruff format" "Run: ruff format backend/"
  fi
else
  skip "ruff format" "no backend/ directory"
fi

# 3. Security scan
if [ -d "backend/" ]; then
  bandit -r backend/ -ll -q 2>/dev/null && pass "bandit security scan" || fail "bandit" "Security issues found. Run: bandit -r backend/ -ll"
else
  skip "bandit" "no backend/ directory"
fi

# 4. Backend tests
if [ -d "backend/tests/" ]; then
  pytest backend/tests/ -v --tb=short 2>&1 && pass "backend tests" || fail "backend tests" "Test failures. See output above."
else
  skip "backend tests" "no backend/tests/ directory"
fi

# 5. Kernel tests
if [ -d "engine/kernel/tests/" ]; then
  PYTHONPATH="${PYTHONPATH:-.}:$(pwd)" pytest engine/kernel/tests/ -v --tb=short 2>&1 && pass "kernel tests" || fail "kernel tests" "Kernel test failures. See output above."
else
  skip "kernel tests" "no engine/kernel/tests/ directory"
fi

# 6. TypeScript checks
if [ -f "package.json" ]; then
  if command -v npx &>/dev/null; then
    npx tsc --noEmit 2>/dev/null && pass "tsc type check" || fail "tsc" "TypeScript errors"
  else
    skip "tsc" "npx not available"
  fi
else
  skip "tsc" "no package.json"
fi

echo ""
echo -e "${GREEN}All local checks passed.${NC}"
