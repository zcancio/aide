"""Tests for L3 → L4 → L3 two-pass escalation in the streaming orchestrator."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.streaming_orchestrator import StreamingOrchestrator


def _make_orch(snapshot=None):
    """Helper to create an orchestrator with a given snapshot."""
    return StreamingOrchestrator(
        aide_id="test",
        snapshot=snapshot or {"entities": {"page": {"display": "page", "props": {"title": "Test"}}}},
        conversation=[],
        api_key="fake",
    )


def _mock_l3_result(text="Budget: $1,350.", tool_calls=None, escalate=False):
    """Build a mock L3 result dict."""
    voice_text = text
    if escalate:
        voice_text = "This needs a new section structure."
    return {
        "text_blocks": [{"text": voice_text}],
        "tool_calls": tool_calls or [],
        "all_raw_tools": tool_calls or [],
        "usage": {"input_tokens": 500, "output_tokens": 100, "cache_read": 4590, "cache_creation": 0},
        "ttfc_ms": 350,
        "ttc_ms": 980,
        "snapshot": {"entities": {"page": {"display": "page", "props": {"title": "Test"}}}},
    }


def _mock_l4_result(text="3 guests confirmed."):
    """Build a mock L4 result dict."""
    return {
        "text_blocks": [{"text": text}],
        "tool_calls": [],
        "all_raw_tools": [{"id": "voice_1", "name": "voice", "input": {"text": text}}],
        "usage": {"input_tokens": 800, "output_tokens": 60, "cache_read": 5491, "cache_creation": 0},
        "ttfc_ms": 600,
        "ttc_ms": 1500,
        "snapshot": {"entities": {"page": {"display": "page", "props": {"title": "Test"}}}},
    }


@pytest.mark.asyncio
async def test_normal_l3_no_escalation():
    """Normal L3 response should NOT trigger L4."""
    orch = _make_orch()
    with patch.object(orch, "_run_tier", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = _mock_l3_result(
            tool_calls=[
                {
                    "name": "mutate_entity",
                    "input": {"action": "update", "ref": "page", "props": {"title": "Updated"}},
                }
            ],
        )
        _ = [e async for e in orch.process_message("update the title")]

    # _run_tier called only once (L3)
    assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_voice_escalation_triggers_l4():
    """L3 voice containing escalation phrase should trigger L4 → L3 two-pass."""
    orch = _make_orch()
    call_count = 0

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_l3_result(escalate=True)
        elif call_count == 2:
            return _mock_l4_result("Expenses section added.")
        else:
            return _mock_l3_result(text="3 expenses tracked.")

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        _ = [e async for e in orch.process_message("let's track expenses")]

    assert call_count == 3  # L3 → L4 → L3


@pytest.mark.asyncio
async def test_structural_creation_triggers_escalation():
    """L3 creating page/section/table/grid should trigger escalation."""
    # Start with existing schema so classifier routes to L3
    orch = _make_orch(snapshot={"entities": {"page": {"display": "page", "props": {"title": "Party"}}}})

    call_tiers = []

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        call_tiers.append(tier)
        if tier == "L3" and len(call_tiers) == 1:
            return _mock_l3_result(
                tool_calls=[
                    {
                        "name": "mutate_entity",
                        "input": {"action": "create", "id": "guests", "display": "section"},
                    }
                ],
            )
        elif tier == "L4":
            return _mock_l4_result("Section created.")
        else:
            return _mock_l3_result(text="Details added.")

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        _ = [e async for e in orch.process_message("add a guests section")]

    assert call_tiers == ["L3", "L4", "L3"]


@pytest.mark.asyncio
async def test_escalation_uses_original_snapshot():
    """L4 should receive the ORIGINAL snapshot, not the L3-mutated one."""
    original_snap = {"entities": {"page": {"display": "page", "props": {"title": "Original"}}}}
    orch = _make_orch(snapshot=original_snap)

    l4_received_snapshot = None

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        nonlocal l4_received_snapshot
        if tier == "L4":
            l4_received_snapshot = snapshot
            return _mock_l4_result()
        elif l4_received_snapshot is None:
            return _mock_l3_result(escalate=True)
        else:
            return _mock_l3_result()

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        _ = [e async for e in orch.process_message("query")]

    assert l4_received_snapshot == original_snap


@pytest.mark.asyncio
async def test_escalation_aggregates_usage():
    """Usage from all passes should be summed in stream.end."""
    orch = _make_orch()

    call_count = 0

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_l3_result(escalate=True)
        elif call_count == 2:
            return _mock_l4_result()
        else:
            return _mock_l3_result()

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        events = [e async for e in orch.process_message("query")]

    end_events = [e for e in events if e.get("type") == "stream.end"]
    assert len(end_events) == 1
    usage = end_events[0]["usage"]
    # L3(500) + L4(800) + L3(500) = 1800
    assert usage["input_tokens"] == 1800
    # L3(100) + L4(60) + L3(100) = 260
    assert usage["output_tokens"] == 260
    # L3(4590) + L4(5491) + L3(4590) = 14671
    assert usage["cache_read"] == 14671


@pytest.mark.asyncio
async def test_escalation_timing():
    """TTFC from first visible pass, TTC spans all passes."""
    orch = _make_orch()

    call_count = 0

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_l3_result(escalate=True)
        elif call_count == 2:
            r = _mock_l4_result()
            r["ttfc_ms"] = 600
            r["ttc_ms"] = 1500
            return r
        else:
            r = _mock_l3_result()
            r["ttfc_ms"] = 300
            r["ttc_ms"] = 900
            return r

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        events = [e async for e in orch.process_message("query")]

    end_events = [e for e in events if e.get("type") == "stream.end"]
    end = end_events[0]
    # TTFC from L4 pass (the visible one)
    assert end["ttfc_ms"] == 600
    # TTC = L3(980) + L4(1500) + L3(900)
    assert end["ttc_ms"] == 980 + 1500 + 900


@pytest.mark.asyncio
async def test_escalation_emits_meta_event():
    """A meta.escalation event should be yielded when escalation occurs."""
    orch = _make_orch()

    call_count = 0

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_l3_result(escalate=True)
        elif call_count == 2:
            return _mock_l4_result()
        else:
            return _mock_l3_result()

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        events = [e async for e in orch.process_message("query")]

    escalation_events = [e for e in events if e.get("type") == "meta.escalation"]
    assert len(escalation_events) == 1
    assert escalation_events[0]["from_tier"] == "L3"
    assert escalation_events[0]["to_tier"] == "L4"


@pytest.mark.asyncio
async def test_escalated_tier_label():
    """stream.end should show tier as 'L3->L4->L3' on escalation."""
    orch = _make_orch()

    call_count = 0

    async def mock_run(tier, snapshot, messages, user_message, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_l3_result(escalate=True)
        elif call_count == 2:
            return _mock_l4_result()
        else:
            return _mock_l3_result()

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        events = [e async for e in orch.process_message("query")]

    end_events = [e for e in events if e.get("type") == "stream.end"]
    assert end_events[0]["tier"] == "L3->L4->L3"


@pytest.mark.asyncio
async def test_l4_temperature_zero():
    """L4 should use temperature 0 for deterministic answers."""
    orch = _make_orch()

    l4_temp = None

    async def mock_run(tier, snapshot, messages, user_message, temperature=None, **kwargs):
        nonlocal l4_temp
        if tier == "L4":
            l4_temp = temperature
            return _mock_l4_result()
        elif l4_temp is None:
            return _mock_l3_result(escalate=True)
        else:
            return _mock_l3_result()

    with patch.object(orch, "_run_tier", side_effect=mock_run):
        _ = [e async for e in orch.process_message("query")]

    assert l4_temp == 0
