"""
Tests for telemetry service and repository.

Repo tests (3):
  test_record_event_creates_row
  test_record_event_with_all_fields
  test_get_aide_stats_aggregates

Telemetry service tests (7):
  test_tracker_records_ttfc
  test_tracker_records_ttc
  test_tracker_records_reducer_stats
  test_tracker_records_escalation
  test_cost_calculation_haiku
  test_cost_calculation_sonnet
  test_cost_calculation_with_cache
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.models.telemetry import TelemetryEvent
from backend.services.telemetry import LLMCallTracker, calculate_cost

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ===========================================================================
# Repository tests (require a running Postgres with the telemetry table)
# ===========================================================================


async def test_record_event_creates_row(initialize_pool) -> None:
    """record_event() returns an integer row id and the row exists in DB."""
    from backend import db
    from backend.repos import telemetry_repo

    aide_id = uuid4()
    event = TelemetryEvent(aide_id=aide_id, event_type="llm_call")

    row_id = await telemetry_repo.record_event(event)
    assert isinstance(row_id, int)
    assert row_id > 0

    # Verify the row is actually in the table
    async with db.system_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM telemetry WHERE id = $1", row_id)
    assert row is not None
    assert str(row["aide_id"]) == str(aide_id)

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM telemetry WHERE id = $1", row_id)


async def test_record_event_with_all_fields(initialize_pool) -> None:
    """record_event() stores all optional fields correctly."""
    from backend import db
    from backend.repos import telemetry_repo

    aide_id = uuid4()
    user_id = uuid4()
    message_id = uuid4()

    event = TelemetryEvent(
        aide_id=aide_id,
        user_id=user_id,
        event_type="llm_call",
        tier="L3",
        model="sonnet",
        prompt_ver="v2.1",
        ttfc_ms=250,
        ttc_ms=1800,
        input_tokens=500,
        output_tokens=120,
        cache_read_tokens=50,
        cache_write_tokens=10,
        lines_emitted=5,
        lines_accepted=4,
        lines_rejected=1,
        escalated=True,
        escalation_reason="new_collection_needed",
        cost_usd=Decimal("0.002500"),
        message_id=message_id,
    )

    row_id = await telemetry_repo.record_event(event)

    async with db.system_conn() as conn:
        row = await conn.fetchrow("SELECT * FROM telemetry WHERE id = $1", row_id)

    assert row["tier"] == "L3"
    assert row["model"] == "sonnet"
    assert row["ttfc_ms"] == 250
    assert row["ttc_ms"] == 1800
    assert row["input_tokens"] == 500
    assert row["output_tokens"] == 120
    assert row["lines_emitted"] == 5
    assert row["lines_accepted"] == 4
    assert row["lines_rejected"] == 1
    assert row["escalated"] is True
    assert row["escalation_reason"] == "new_collection_needed"

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM telemetry WHERE id = $1", row_id)


async def test_get_aide_stats_aggregates(initialize_pool) -> None:
    """get_aide_stats() returns correct aggregate counts and sums."""
    from backend import db
    from backend.repos import telemetry_repo

    aide_id = uuid4()

    # Insert 2 L2 calls
    ids = []
    for _ in range(2):
        event = TelemetryEvent(
            aide_id=aide_id,
            event_type="llm_call",
            tier="L2",
            model="haiku",
            ttfc_ms=100,
            lines_emitted=3,
            lines_accepted=3,
            lines_rejected=0,
            cost_usd=Decimal("0.001"),
        )
        ids.append(await telemetry_repo.record_event(event))

    # Insert 1 L3 escalation
    escalation_event = TelemetryEvent(
        aide_id=aide_id,
        event_type="llm_call",
        tier="L3",
        model="sonnet",
        ttfc_ms=500,
        escalated=True,
        escalation_reason="schema_missing",
        cost_usd=Decimal("0.030"),
    )
    ids.append(await telemetry_repo.record_event(escalation_event))

    stats = await telemetry_repo.get_aide_stats(aide_id)

    assert stats["llm_calls"] == 3
    assert stats["direct_edits"] == 0
    assert stats["escalations"] == 1
    assert abs(float(stats["avg_l2_ttfc"]) - 100.0) < 1
    assert abs(float(stats["avg_l3_ttfc"]) - 500.0) < 1
    assert abs(float(stats["total_cost"]) - 0.032) < 0.0001
    # accept_rate = 6 accepted / 6 emitted = 1.0
    assert abs(float(stats["accept_rate"]) - 1.0) < 0.001

    # Cleanup
    async with db.system_conn() as conn:
        await conn.execute("DELETE FROM telemetry WHERE id = ANY($1::int[])", ids)


# ===========================================================================
# Telemetry service — pure unit tests (no DB)
# ===========================================================================


async def test_tracker_records_ttfc() -> None:
    """LLMCallTracker.mark_first_content() sets ttfc_ms correctly."""
    with patch("backend.services.telemetry.telemetry_repo") as mock_repo:
        mock_repo.record_event = AsyncMock(return_value=1)

        tracker = LLMCallTracker(aide_id=uuid4(), user_id=uuid4(), tier="L2", model="haiku")
        tracker.start()
        await asyncio.sleep(0.05)
        tracker.mark_first_content()
        await tracker.finish()

        event = mock_repo.record_event.call_args[0][0]
        assert event.ttfc_ms is not None
        assert event.ttfc_ms >= 40  # at least ~40ms


async def test_tracker_records_ttc() -> None:
    """LLMCallTracker.finish() sets ttc_ms >= ttfc_ms."""
    with patch("backend.services.telemetry.telemetry_repo") as mock_repo:
        mock_repo.record_event = AsyncMock(return_value=1)

        tracker = LLMCallTracker(aide_id=uuid4(), user_id=uuid4(), tier="L2", model="haiku")
        tracker.start()
        await asyncio.sleep(0.03)
        tracker.mark_first_content()
        await asyncio.sleep(0.02)
        await tracker.finish()

        event = mock_repo.record_event.call_args[0][0]
        assert event.ttc_ms is not None
        assert event.ttfc_ms is not None
        assert event.ttc_ms >= event.ttfc_ms


async def test_tracker_records_reducer_stats() -> None:
    """set_reducer_stats() propagates to the TelemetryEvent."""
    with patch("backend.services.telemetry.telemetry_repo") as mock_repo:
        mock_repo.record_event = AsyncMock(return_value=1)

        tracker = LLMCallTracker(aide_id=uuid4(), user_id=uuid4(), tier="L2", model="haiku")
        tracker.start()
        tracker.set_reducer_stats(emitted=10, accepted=8, rejected=2)
        await tracker.finish()

        event = mock_repo.record_event.call_args[0][0]
        assert event.lines_emitted == 10
        assert event.lines_accepted == 8
        assert event.lines_rejected == 2


async def test_tracker_records_escalation() -> None:
    """set_escalation() sets escalated=True and stores the reason."""
    with patch("backend.services.telemetry.telemetry_repo") as mock_repo:
        mock_repo.record_event = AsyncMock(return_value=1)

        tracker = LLMCallTracker(aide_id=uuid4(), user_id=uuid4(), tier="L3", model="sonnet")
        tracker.start()
        tracker.set_escalation("unknown_field")
        await tracker.finish()

        event = mock_repo.record_event.call_args[0][0]
        assert event.escalated is True
        assert event.escalation_reason == "unknown_field"


# ===========================================================================
# calculate_cost — pure unit tests (synchronous)
# ===========================================================================


def test_cost_calculation_haiku() -> None:
    """Haiku cost: 1M input = $0.25, 1M output = $1.25."""
    cost = calculate_cost("haiku", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == Decimal("1.500000")


def test_cost_calculation_sonnet() -> None:
    """Sonnet cost: 1M input = $3.00, 1M output = $15.00."""
    cost = calculate_cost("sonnet", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == Decimal("18.000000")


def test_cost_calculation_with_cache() -> None:
    """Cache-read tokens are billed at reduced rate (haiku: $0.03/M)."""
    # 1M input, all cache-read → regular_input = 0
    cost = calculate_cost(
        "haiku",
        input_tokens=1_000_000,
        output_tokens=0,
        cache_read_tokens=1_000_000,
    )
    # cache_read: 1M * $0.03/M = $0.03
    assert cost == Decimal("0.030000")
