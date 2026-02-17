"""Service to read and aggregate flight recorder data from R2."""

from __future__ import annotations

import json
from typing import Any

from backend.services.r2 import r2_service


class FlightRecorderReader:
    """Service to read and aggregate flight recorder data from R2."""

    async def get_all_turns(self, aide_id: str) -> list[dict[str, Any]]:
        """
        Fetch all turn records for an aide, sorted by timestamp.

        Args:
            aide_id: Aide ID

        Returns:
            List of TurnRecord dicts, sorted chronologically with turn_index added
        """
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

        return all_turns

    async def get_turn_by_index(self, aide_id: str, turn_index: int) -> dict[str, Any] | None:
        """
        Fetch a specific turn by index.

        This re-fetches all turns and returns the one at the given index.
        Could be optimized with caching in future.

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


# Singleton instance
flight_recorder_reader = FlightRecorderReader()
