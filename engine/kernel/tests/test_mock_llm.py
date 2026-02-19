"""Tests for MockLLM — deterministic streaming with configurable delays."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from engine.kernel.mock_llm import MockLLM

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> MockLLM:
    """MockLLM pointed at the real golden directory."""
    golden_dir = Path(__file__).parent / "fixtures" / "golden"
    return MockLLM(golden_dir=golden_dir)


@pytest.fixture
def mock_llm_tmp(tmp_path: Path) -> MockLLM:
    """MockLLM pointed at a temporary directory for custom fixtures."""
    return MockLLM(golden_dir=tmp_path)


# ---------------------------------------------------------------------------
# test_streams_golden_file_lines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streams_golden_file_lines(mock_llm: MockLLM) -> None:
    """All non-empty lines from a golden file are yielded."""
    lines = []
    async for line in mock_llm.stream("update_simple", profile="instant"):
        lines.append(line)

    golden_path = Path(__file__).parent / "fixtures" / "golden" / "update_simple.jsonl"
    expected = [ln for ln in golden_path.read_text().splitlines() if ln.strip()]

    assert lines == expected
    assert len(lines) > 0


# ---------------------------------------------------------------------------
# test_instant_profile_no_delay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instant_profile_no_delay(mock_llm: MockLLM) -> None:
    """Instant profile completes in under 200ms (no sleep calls)."""
    # create_graduation has 23 lines — use it to stress-test instant mode
    start = time.perf_counter()
    async for _ in mock_llm.stream("create_graduation", profile="instant"):
        pass
    elapsed_ms = (time.perf_counter() - start) * 1000
    # Allow 200ms for slow CI runners; the key is no asyncio.sleep()
    assert elapsed_ms < 200, f"Instant profile took {elapsed_ms:.1f}ms — should be near zero"


# ---------------------------------------------------------------------------
# test_realistic_l2_timing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_realistic_l2_timing(mock_llm: MockLLM) -> None:
    """
    realistic_l2 profile: ~200ms think time + ~50ms per-line.
    With update_simple (1 line): total ≈ 200ms (no per-line delay after last line).
    Expect at least 160ms (80% margin for CI scheduling variance).
    """
    start = time.perf_counter()
    async for _ in mock_llm.stream("update_simple", profile="realistic_l2"):
        pass
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms >= 160, f"realistic_l2 only took {elapsed_ms:.1f}ms — expected ≥160ms"


# ---------------------------------------------------------------------------
# test_realistic_l3_timing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_realistic_l3_timing(mock_llm: MockLLM) -> None:
    """
    realistic_l3 profile: ~800ms think time + ~100ms per-line.
    With update_simple (1 line): total ≈ 800ms.
    Expect at least 640ms (80% margin).
    """
    start = time.perf_counter()
    async for _ in mock_llm.stream("update_simple", profile="realistic_l3"):
        pass
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms >= 640, f"realistic_l3 only took {elapsed_ms:.1f}ms — expected ≥640ms"


# ---------------------------------------------------------------------------
# test_missing_golden_file_raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_golden_file_raises(mock_llm: MockLLM) -> None:
    """FileNotFoundError raised when scenario golden file does not exist."""
    with pytest.raises(FileNotFoundError, match="no_such_scenario"):
        async for _ in mock_llm.stream("no_such_scenario", profile="instant"):
            pass


# ---------------------------------------------------------------------------
# test_skips_empty_lines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skips_empty_lines(mock_llm_tmp: MockLLM, tmp_path: Path) -> None:
    """Empty and whitespace-only lines are not yielded."""
    golden = tmp_path / "with_blanks.jsonl"
    golden.write_text('{"t":"entity.create","id":"a"}\n\n   \n{"t":"entity.create","id":"b"}\n')

    lines = []
    async for line in mock_llm_tmp.stream("with_blanks", profile="instant"):
        lines.append(line)

    assert len(lines) == 2
    assert all(line.strip() for line in lines)
