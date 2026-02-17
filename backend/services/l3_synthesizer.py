"""L3 Synthesizer — Schema synthesis using Sonnet."""

import json
from pathlib import Path
from typing import Any

from backend.services.ai_provider import ai_provider
from engine.kernel.primitives import validate_primitive
from engine.kernel.types import Event, Snapshot


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
            model="claude-sonnet-4-20250514",
            system=self.system_prompt,
            messages=messages,
            max_tokens=16384,  # Increased for large entity batches (grids, etc.)
            temperature=1.0,
        )

        # Parse JSON response (strip markdown code blocks if present)
        content = result["content"].strip()
        if content.startswith("```"):
            # Remove markdown fencing
            lines = content.split("\n")
            # Remove first line (```json) and last line (```)
            content = "\n".join(lines[1:-1])

        try:
            response_data = json.loads(content)
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
            errors = validate_primitive(primitive.get("type", ""), primitive.get("payload", {}))
            if errors:
                # Skip invalid primitive, log error
                print(f"L3 emitted invalid primitive: {errors[0]}")
                continue
            validated_primitives.append(primitive)

        return {
            "primitives": validated_primitives,
            "response": response_data.get("response", ""),
        }

    def _build_user_message(self, message: str, snapshot: Snapshot, recent_events: list[Event]) -> str:
        """Build user message with snapshot and event context."""
        # Serialize snapshot
        snapshot_json = json.dumps(snapshot.to_dict(), indent=2)

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
