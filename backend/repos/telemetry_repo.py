"""Repository for telemetry event persistence."""

from __future__ import annotations

import json
from uuid import UUID

from backend.db import system_conn, user_conn
from backend.models.telemetry import TelemetryEvent, TokenUsage, TurnTelemetry


async def record_event(event: TelemetryEvent) -> int:
    """Insert a telemetry event row. Returns the new row id."""
    async with system_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO telemetry (
                aide_id, user_id, event_type,
                tier, model, prompt_ver,
                ttfc_ms, ttc_ms,
                input_tokens, output_tokens,
                cache_read_tokens, cache_write_tokens,
                lines_emitted, lines_accepted, lines_rejected,
                escalated, escalation_reason,
                cost_usd, edit_latency_ms,
                message_id, error
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            ) RETURNING id
            """,
            event.aide_id,
            event.user_id,
            event.event_type,
            event.tier,
            event.model,
            event.prompt_ver,
            event.ttfc_ms,
            event.ttc_ms,
            event.input_tokens,
            event.output_tokens,
            event.cache_read_tokens,
            event.cache_write_tokens,
            event.lines_emitted,
            event.lines_accepted,
            event.lines_rejected,
            event.escalated,
            event.escalation_reason,
            event.cost_usd,
            event.edit_latency_ms,
            event.message_id,
            event.error,
        )
        return row["id"]


async def get_aide_stats(aide_id: UUID) -> dict:
    """Return aggregate telemetry stats for a single aide."""
    async with system_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'llm_call')    AS llm_calls,
                COUNT(*) FILTER (WHERE event_type = 'direct_edit') AS direct_edits,
                COUNT(*) FILTER (WHERE escalated = true)           AS escalations,
                AVG(ttfc_ms) FILTER (WHERE tier = 'L2')            AS avg_l2_ttfc,
                AVG(ttfc_ms) FILTER (WHERE tier = 'L3')            AS avg_l3_ttfc,
                SUM(cost_usd)                                       AS total_cost,
                SUM(lines_accepted)::float
                    / NULLIF(SUM(lines_emitted), 0)                AS accept_rate
            FROM telemetry
            WHERE aide_id = $1
            """,
            aide_id,
        )
        return dict(row)


async def insert_turn(
    user_id: UUID,
    aide_id: UUID,
    turn: TurnTelemetry,
) -> UUID:
    """Insert a turn telemetry record. Returns row ID."""
    async with user_conn(user_id) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO aide_turn_telemetry (
                aide_id, user_id, turn_num, tier, model, message,
                tool_calls, text_blocks, system_prompt, usage,
                ttfc_ms, ttc_ms, validation
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING id
            """,
            aide_id,
            user_id,
            turn.turn,
            turn.tier,
            turn.model,
            turn.message,
            json.dumps(turn.tool_calls),
            json.dumps(turn.text_blocks),
            turn.system_prompt,
            json.dumps(turn.usage.model_dump()),
            turn.ttfc_ms,
            turn.ttc_ms,
            json.dumps(turn.validation) if turn.validation else None,
        )
        return row["id"]


async def get_turns_for_aide(
    user_id: UUID,
    aide_id: UUID,
) -> list[TurnTelemetry]:
    """Get all turns for an aide, ordered by turn number."""
    async with user_conn(user_id) as conn:
        rows = await conn.fetch(
            """
            SELECT turn_num, tier, model, message, tool_calls, text_blocks,
                   system_prompt, usage, ttfc_ms, ttc_ms, validation
            FROM aide_turn_telemetry
            WHERE aide_id = $1
            ORDER BY turn_num
            """,
            aide_id,
        )
        return [
            TurnTelemetry(
                turn=r["turn_num"],
                tier=r["tier"],
                model=r["model"],
                message=r["message"],
                tool_calls=json.loads(r["tool_calls"]),
                text_blocks=json.loads(r["text_blocks"]),
                system_prompt=r["system_prompt"],
                usage=TokenUsage(**json.loads(r["usage"])),
                ttfc_ms=r["ttfc_ms"],
                ttc_ms=r["ttc_ms"],
                validation=json.loads(r["validation"]) if r["validation"] else None,
            )
            for r in rows
        ]
