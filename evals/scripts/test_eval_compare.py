#!/usr/bin/env python3
"""
Tests for eval_compare.py
"""

import json
import sys
import tempfile
from io import StringIO
from pathlib import Path


def test_compare_runs_outputs_table():
    """eval_compare must output a comparison table."""
    from eval_compare import compare_runs

    # Create mock run directories
    with tempfile.TemporaryDirectory() as tmpdir:
        run_a = Path(tmpdir) / "run_a"
        run_b = Path(tmpdir) / "run_b"
        run_a.mkdir()
        run_b.mkdir()

        (run_a / "report.json").write_text(
            json.dumps(
                {
                    "timestamp": "2026-03-01T10:00:00",
                    "overall_average": 0.85,
                    "results": [
                        {
                            "name": "test_scenario",
                            "avg_score": 0.85,
                            "total_tokens": 1000,
                            "tier_accuracy": 0.90,
                            "turns": [],
                        }
                    ],
                }
            )
        )
        (run_b / "report.json").write_text(
            json.dumps(
                {
                    "timestamp": "2026-03-01T11:00:00",
                    "overall_average": 0.90,
                    "results": [
                        {
                            "name": "test_scenario",
                            "avg_score": 0.90,
                            "total_tokens": 900,
                            "tier_accuracy": 0.92,
                            "turns": [],
                        }
                    ],
                }
            )
        )

        output = StringIO()
        sys.stdout = output
        compare_runs(run_a, run_b)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "EVAL COMPARISON" in result
        assert "test_scenario" in result
        # Check for delta (either +5.0% or +0.05 or similar)
        assert "+5" in result or "+0.05" in result


def test_compare_runs_shows_regressions():
    """eval_compare must highlight regressions."""
    from eval_compare import compare_runs

    with tempfile.TemporaryDirectory() as tmpdir:
        run_a = Path(tmpdir) / "run_a"
        run_b = Path(tmpdir) / "run_b"
        run_a.mkdir()
        run_b.mkdir()

        (run_a / "report.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "name": "regression_test",
                            "avg_score": 0.90,
                            "total_tokens": 1000,
                            "turns": [],
                        }
                    ]
                }
            )
        )
        (run_b / "report.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "name": "regression_test",
                            "avg_score": 0.85,
                            "total_tokens": 1000,
                            "turns": [],
                        }
                    ]
                }
            )
        )

        output = StringIO()
        sys.stdout = output
        compare_runs(run_a, run_b)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "Regressions" in result
        assert "regression_test" in result


def test_compare_runs_shows_improvements():
    """eval_compare must highlight improvements."""
    from eval_compare import compare_runs

    with tempfile.TemporaryDirectory() as tmpdir:
        run_a = Path(tmpdir) / "run_a"
        run_b = Path(tmpdir) / "run_b"
        run_a.mkdir()
        run_b.mkdir()

        (run_a / "report.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "name": "improvement_test",
                            "avg_score": 0.80,
                            "total_tokens": 1000,
                            "turns": [],
                        }
                    ]
                }
            )
        )
        (run_b / "report.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "name": "improvement_test",
                            "avg_score": 0.85,
                            "total_tokens": 900,
                            "turns": [],
                        }
                    ]
                }
            )
        )

        output = StringIO()
        sys.stdout = output
        compare_runs(run_a, run_b)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "Improvements" in result
        assert "improvement_test" in result


if __name__ == "__main__":
    test_compare_runs_outputs_table()
    test_compare_runs_shows_regressions()
    test_compare_runs_shows_improvements()
    print("All tests passed!")
