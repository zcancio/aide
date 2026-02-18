"""Service to read and aggregate flight recorder data from R2."""

from __future__ import annotations

import json
import time
from typing import Any

from backend.services.r2 import r2_service

# Simple TTL cache: {aide_id: (timestamp, turns)}
_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
CACHE_TTL_SECONDS = 60  # Cache for 1 minute


class FlightRecorderReader:
    """Service to read and aggregate flight recorder data from R2."""

    async def get_all_turns(self, aide_id: str, force_refresh: bool = False) -> list[dict[str, Any]]:
        """
        Fetch all turn records for an aide, sorted by timestamp.

        Uses in-memory cache to avoid repeated R2 fetches.

        Args:
            aide_id: Aide ID
            force_refresh: If True, bypass cache

        Returns:
            List of TurnRecord dicts, sorted chronologically with turn_index added
        """
        # Check cache
        if not force_refresh and aide_id in _cache:
            cached_time, cached_turns = _cache[aide_id]
            if time.time() - cached_time < CACHE_TTL_SECONDS:
                return cached_turns

        # List all JSONL files for this aide
        keys = await r2_service.list_flight_logs(aide_id)

        all_turns: list[dict[str, Any]] = []
        for key in keys:
            content = await r2_service.get_flight_log(key)
            if content:
                # Parse JSONL (each line is a TurnRecord)
                for line in content.strip().split("\n"):
                    if line:
                        try:
                            turn = json.loads(line)
                            all_turns.append(turn)
                        except json.JSONDecodeError:
                            continue

        # Sort by timestamp
        all_turns.sort(key=lambda t: t.get("timestamp", ""))

        # Add sequential index
        for i, turn in enumerate(all_turns):
            turn["turn_index"] = i

        # Update cache
        _cache[aide_id] = (time.time(), all_turns)

        return all_turns

    async def get_turn_by_index(self, aide_id: str, turn_index: int) -> dict[str, Any] | None:
        """
        Fetch a specific turn by index.

        Uses cached turns from get_all_turns.

        Args:
            aide_id: Aide ID
            turn_index: Zero-based turn index

        Returns:
            TurnRecord dict or None if not found
        """
        all_turns = await self.get_all_turns(aide_id)
        if 0 <= turn_index < len(all_turns):
            return all_turns[turn_index]
        return None

    def invalidate_cache(self, aide_id: str) -> None:
        """Clear cache for a specific aide."""
        if aide_id in _cache:
            del _cache[aide_id]


# Singleton instance
flight_recorder_reader = FlightRecorderReader()
