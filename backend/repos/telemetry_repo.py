"""Repository for telemetry event persistence."""

from __future__ import annotations

from uuid import UUID

from backend.db import system_conn
from backend.models.telemetry import TelemetryEvent


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
