"""Flight recorder replay routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from backend.auth import get_current_user
from backend.models.flight_recorder import (
    FlightRecorderListResponse,
    LLMCallSummary,
    TurnSummary,
)
from backend.models.user import User
from backend.repos.aide_repo import AideRepo
from backend.services.flight_recorder_reader import flight_recorder_reader
from backend.services.flight_recorder_uploader import flight_recorder_uploader
from backend.services.orchestrator import orchestrator
from engine.kernel.react_preview import render_react_preview

router = APIRouter(prefix="/api/flight-recorder", tags=["flight-recorder"])
aide_repo = AideRepo()


@router.get("/{aide_id}", status_code=200)
async def list_turns(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> FlightRecorderListResponse:
    """
    List all turns for an aide's flight recorder.

    Returns turn summaries (without snapshot data) for display in timeline.
    """
    # Verify user owns this aide (RLS check)
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Fetch all turns from R2
    turns = await flight_recorder_reader.get_all_turns(str(aide_id))

    # Convert to summary format (exclude snapshot data)
    turn_summaries = [
        TurnSummary(
            turn_id=t["turn_id"],
            turn_index=t["turn_index"],
            timestamp=t["timestamp"],
            source=t["source"],
            user_message=t["user_message"],
            response_text=t["response_text"],
            llm_calls=[
                LLMCallSummary(
                    call_id=c["call_id"],
                    shadow=c["shadow"],
                    model=c["model"],
                    tier=c["tier"],
                    latency_ms=c["latency_ms"],
                    prompt=c.get("prompt", ""),
                    response=c.get("response", ""),
                    usage=c.get("usage", {}),
                    error=c.get("error"),
                )
                for c in t.get("llm_calls", [])
            ],
            primitives_emitted=t.get("primitives_emitted", []),
            primitives_applied=t.get("primitives_applied", 0),
            total_latency_ms=t.get("total_latency_ms", 0),
            error=t.get("error"),
        )
        for t in turns
    ]

    return FlightRecorderListResponse(
        aide_id=str(aide_id),
        aide_title=aide.title,
        turns=turn_summaries,
    )


@router.get("/{aide_id}/render", status_code=200)
async def render_turn(
    aide_id: UUID,
    turn_index: int = Query(..., ge=0),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """
    Render the HTML preview for a specific turn.

    Uses snapshot_after from the turn record.
    """
    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Fetch the specific turn
    turn = await flight_recorder_reader.get_turn_by_index(str(aide_id), turn_index)
    if not turn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn not found.")

    # Render the snapshot_after
    snapshot = turn.get("snapshot_after", {})
    title = snapshot.get("meta", {}).get("title") or aide.title
    html_content = render_react_preview(snapshot, title=title)

    return HTMLResponse(content=html_content)


@router.get("/{aide_id}/export", status_code=200)
async def export_turn(
    aide_id: UUID,
    turn_index: int = Query(..., ge=0),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Export full turn data as JSON for debugging/analysis.

    Includes snapshots, LLM calls with full prompts/responses, and all metadata.
    """
    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Fetch the specific turn
    turn = await flight_recorder_reader.get_turn_by_index(str(aide_id), turn_index)
    if not turn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn not found.")

    # Return full turn data
    return turn


@router.post("/{aide_id}/replay", status_code=200)
async def replay_turn(
    aide_id: UUID,
    turn_index: int = Query(..., ge=0),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Replay a turn with current models/prompts (dry run - no persistence).

    Re-runs the AI calls using the original snapshot_before and user_message,
    returning what the current models would produce without saving anything.
    Useful for debugging model behavior and comparing with original results.
    """
    # Verify user owns this aide
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aide not found.")

    # Fetch the specific turn
    turn = await flight_recorder_reader.get_turn_by_index(str(aide_id), turn_index)
    if not turn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn not found.")

    # Replay the turn (dry run)
    result = await orchestrator.replay_turn(turn)

    return result


@router.post("/flush", status_code=200)
async def flush_recorder(
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Force flush pending flight recorder records to R2.

    Debug endpoint for local development.
    """
    await flight_recorder_uploader.flush()
    return {"status": "flushed"}
