"""L2 Compiler — Intent compilation using Haiku."""

import json
from pathlib import Path
from typing import Any

from backend.services.ai_provider import ai_provider
from engine.kernel.primitives import validate_primitive
from engine.kernel.types import Event, Snapshot


class L2Compiler:
    """L2 (Haiku) intent compilation service."""

    def __init__(self) -> None:
        """Initialize L2 with system prompt."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "l2_system.md"
        with open(prompt_path) as f:
            self.system_prompt = f.read()

    async def compile(
        self,
        message: str,
        snapshot: Snapshot,
        recent_events: list[Event],
    ) -> dict[str, Any]:
        """
        Compile user message into primitive events.

        Args:
            message: User message
            snapshot: Current aide state
            recent_events: Recent event log for context

        Returns:
            Dict with:
            - primitives: list of primitive events
            - response: response text to show user
            - escalate: bool indicating if L3 is needed
        """
        # Build user message with context
        user_content = self._build_user_message(message, snapshot, recent_events)

        # Call Haiku
        messages = [{"role": "user", "content": user_content}]

        from backend.config import settings

        result = await ai_provider.call_claude(
            model=settings.L2_MODEL,
            system=self.system_prompt,
            messages=messages,
            max_tokens=4096,
            temperature=1.0,
        )

        # Parse JSON response (extract from markdown code blocks if present)
        content = result["content"].strip()

        # Try to extract JSON from markdown code block anywhere in response
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        raw_response = result["content"]
        usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})

        try:
            response_data = json.loads(content)
        except json.JSONDecodeError as e:
            # L2 failed to return valid JSON — escalate to L3
            print(f"L2 invalid JSON, escalating: {e}")
            print(f"L2 raw content (first 500): {raw_response[:500]}")
            return {
                "primitives": [],
                "response": "",
                "escalate": True,
                "error": f"L2 returned invalid JSON: {e}",
                "_raw_response": raw_response,
                "usage": usage,
            }

        primitives_count = len(response_data.get("primitives", []))
        print(f"L2 response: escalate={response_data.get('escalate')}, primitives={primitives_count}")
        for p in response_data.get("primitives", []):
            print(f"  L2 primitive: {p.get('type')} -> {p.get('payload')}")

        # Check if L2 is requesting escalation
        if response_data.get("escalate", False):
            return {
                "primitives": [],
                "response": "",
                "escalate": True,
                "_raw_response": raw_response,
                "usage": usage,
            }

        # Validate primitives
        primitives = response_data.get("primitives", [])
        validated_primitives = []

        for primitive in primitives:
            errors = validate_primitive(primitive.get("type", ""), primitive.get("payload", {}))
            if errors:
                # Invalid primitive — escalate to L3
                print(f"L2 emitted invalid primitive: {errors[0]}")
                return {
                    "primitives": [],
                    "response": "",
                    "escalate": True,
                    "_raw_response": raw_response,
                    "usage": usage,
                }
            validated_primitives.append(primitive)

        return {
            "primitives": validated_primitives,
            "response": response_data.get("response", ""),
            "escalate": False,
            "_raw_response": raw_response,
            "usage": usage,
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

Return a JSON object with "primitives" (array of primitive events), "response" (brief state
reflection), and "escalate" (boolean).
"""


# Singleton instance
l2_compiler = L2Compiler()
