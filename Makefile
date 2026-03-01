.PHONY: test lint eval-smoke eval-full

# ── Dev ──────────────────────────────────────────────────────────────────────

lint:
	ruff check backend/ engine/
	ruff format --check backend/ engine/

test:
	pytest backend/tests/ engine/kernel/tests/ -v --tb=short

# ── Eval ─────────────────────────────────────────────────────────────────────

# Quick smoke test: 3 turns of graduation scenario (~$0.03, ~60s)
eval-smoke:
	@echo "Running eval smoke test (3 turns, graduation_realistic)..."
	python evals/scripts/eval_multiturn.py --scenario graduation_realistic --turns 3 --save
	@echo "Running smoke assertions..."
	pytest evals/tests/test_eval_smoke.py -v --tb=short

# Full eval: all scenarios, all turns (~$0.50, ~5min)
eval-full:
	python evals/scripts/eval_multiturn.py
