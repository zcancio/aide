"""Tests for telemetry Pydantic models."""

from backend.models.telemetry import AideTelemetry, TokenUsage, TurnTelemetry


def test_token_usage_cost_l3():
    usage = TokenUsage(input_tokens=1000, output_tokens=500, cache_read=200)
    cost = usage.cost("L3")
    # (1000 * 3 + 500 * 15 + 200 * 0.3) / 1e6
    assert abs(cost - 0.01056) < 0.0001


def test_token_usage_cost_l4():
    usage = TokenUsage(input_tokens=1000, output_tokens=500, cache_read=0, cache_creation=100)
    cost = usage.cost("L4")
    # (1000 * 5 + 500 * 25 + 100 * 6.25) / 1e6
    assert abs(cost - 0.018125) < 0.0001


def test_turn_telemetry_validates():
    turn = TurnTelemetry(
        turn=1,
        tier="L3",
        model="claude-sonnet-4-5-20250929",
        message="test",
        tool_calls=[],
        text_blocks=[],
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        ttfc_ms=200,
        ttc_ms=1000,
    )
    assert turn.turn == 1


def test_aide_telemetry_serializes():
    aide = AideTelemetry(
        aide_id="abc",
        name="Test",
        timestamp="2026-01-01T00:00:00Z",
        turns=[],
    )
    data = aide.model_dump()
    assert data["aide_id"] == "abc"
