"""L3 Synthesizer — Schema synthesis using Sonnet."""

import json
from pathlib import Path
from typing import Any

from backend.services.ai_provider import ai_provider
from engine.kernel.types import Event, Snapshot
from engine.kernel.validator import validate_primitive


class L3Synthesizer:
    """L3 (Sonnet) schema synthesis service."""

    def __init__(self) -> None:
        """Initialize L3 with system prompt."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "l3_system.md"
        with open(prompt_path) as f:
            self.system_prompt = f.read()

    async def synthesize(
        self,
        message: str,
        snapshot: Snapshot,
        recent_events: list[Event],
        image_data: bytes | None = None,
    ) -> dict[str, Any]:
        """
        Synthesize schema and entities from user message.

        Args:
            message: User message
            snapshot: Current aide state
            recent_events: Recent event log for context
            image_data: Optional image bytes (base64 encoded in request)

        Returns:
            Dict with:
            - primitives: list of primitive events
            - response: response text to show user
        """
        # Build user message with context
        user_content = self._build_user_message(message, snapshot, recent_events)

        # Call Sonnet
        messages = [{"role": "user", "content": user_content}]

        result = await ai_provider.call_claude(
            model="claude-3-5-sonnet-20241022",
            system=self.system_prompt,
            messages=messages,
            max_tokens=4096,
            temperature=1.0,
        )

        # Parse JSON response
        try:
            response_data = json.loads(result["content"])
        except json.JSONDecodeError as e:
            # L3 failed to return valid JSON — return empty result
            return {
                "primitives": [],
                "response": "",
                "error": f"L3 returned invalid JSON: {e}",
            }

        # Validate primitives
        primitives = response_data.get("primitives", [])
        validated_primitives = []

        for primitive in primitives:
            try:
                validate_primitive(primitive)
                validated_primitives.append(primitive)
            except ValueError as e:
                # Skip invalid primitive, log error
                print(f"L3 emitted invalid primitive: {e}")
                continue

        return {
            "primitives": validated_primitives,
            "response": response_data.get("response", ""),
        }

    def _build_user_message(self, message: str, snapshot: Snapshot, recent_events: list[Event]) -> str:
        """Build user message with snapshot and event context."""
        # Serialize snapshot
        snapshot_json = json.dumps(
            {
                "collections": snapshot.collections,
                "entities": snapshot.entities,
                "blocks": snapshot.blocks,
                "views": snapshot.views,
                "styles": snapshot.styles,
                "meta": snapshot.meta,
                "relationships": snapshot.relationships,
            },
            indent=2,
        )

        # Serialize recent events (last 10)
        events_json = json.dumps(
            [
                {
                    "type": e.type,
                    "payload": e.payload,
                    "timestamp": e.timestamp,
                }
                for e in recent_events[-10:]
            ],
            indent=2,
        )

        return f"""User message: {message}

Current snapshot:
{snapshot_json}

Recent events:
{events_json}

Return a JSON object with "primitives" (array of primitive events) and "response" (brief state reflection).
"""


# Singleton instance
l3_synthesizer = L3Synthesizer()
