"""L3 Synthesizer — Schema synthesis using Sonnet."""

import json
from typing import Any

from backend.services.ai_provider import ai_provider
from backend.services.prompt_builder import build_l3_prompt
from engine.kernel.primitives import validate_primitive
from engine.kernel.types import Event


class L3Synthesizer:
    """L3 (Sonnet) schema synthesis service."""

    def __init__(self) -> None:
        """Initialize L3 synthesizer."""
        pass

    async def synthesize(
        self,
        message: str,
        snapshot: dict[str, Any],
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
        # Build system prompt with new prompt builder
        system_prompt = build_l3_prompt(snapshot)

        # Build user message with context
        user_content = self._build_user_message(message, snapshot, recent_events)

        # Call Sonnet
        messages = [{"role": "user", "content": user_content}]

        result = await ai_provider.call_claude(
            model="claude-sonnet-4-20250514",
            system=system_prompt,
            messages=messages,
            max_tokens=16384,  # Increased for large entity batches (grids, etc.)
            temperature=0.0,
        )

        # Parse JSONL response (one JSON object per line)
        content = result["content"].strip()
        raw_response = result["content"]
        usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})

        # Remove markdown code blocks if present
        if "```" in content:
            # Extract content between code blocks
            lines = []
            in_code_block = False
            for line in content.split("\n"):
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or not line.strip().startswith("```"):
                    lines.append(line)
            content = "\n".join(lines)

        # Parse JSONL format
        primitives = []
        response_text = ""

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = obj.get("t", "")

            # Handle voice line (response text)
            if event_type == "voice":
                response_text = obj.get("text", "")
                continue

            # Skip if no event type
            if not event_type:
                # Try old format (JSON wrapper) for backward compatibility
                if "primitives" in obj:
                    # Old format detected
                    primitives = obj.get("primitives", [])
                    response_text = obj.get("response", "")
                    break
                continue

            # Convert JSONL format to primitive format
            primitive = self._jsonl_to_primitive(obj)
            if primitive:
                primitives.append(primitive)

        print(f"L3 parsed: {len(primitives)} primitives, response='{response_text[:50]}'")

        # Validate primitives
        validated_primitives = []

        for primitive in primitives:
            ptype = primitive.get("type", "")
            payload = primitive.get("payload", {})
            errors = validate_primitive(ptype, payload)
            if errors:
                # Skip invalid primitive, log error
                print(f"L3 emitted invalid primitive: {errors[0]}")
                continue
            validated_primitives.append(primitive)

        return {
            "primitives": validated_primitives,
            "response": response_text,
            "_raw_response": raw_response,
            "usage": usage,
        }

    def _jsonl_to_primitive(self, obj: dict) -> dict | None:
        """Convert JSONL shorthand to full primitive format."""
        event_type = obj.get("t", "")
        if not event_type:
            return None

        # Build payload based on event type
        payload: dict[str, Any] = {}

        if event_type == "collection.create":
            payload = {
                "id": obj.get("id", ""),
                "name": obj.get("name", ""),
                "schema": obj.get("schema", {}),
            }
        elif event_type == "entity.create":
            # Support both v1 (collection) and v2 (parent) formats
            parent = obj.get("parent", "")
            collection = obj.get("collection", "")
            props = obj.get("p", {})

            # If parent is "root", this is a top-level entity - convert to collection.create
            if parent == "root" or (not collection and not parent):
                # Convert to collection.create for v1 reducer compatibility
                return {
                    "type": "collection.create",
                    "payload": {
                        "id": obj.get("id", ""),
                        "name": props.get("title", props.get("name", obj.get("id", ""))),
                        "schema": {},  # Will be inferred from entities
                    },
                }

            # Use parent as collection if collection not provided (v2 format)
            effective_collection = collection or parent
            payload = {
                "collection": effective_collection,
                "id": obj.get("id", ""),
                "fields": props,
            }
            # Pass through display hint if present
            if "display" in obj:
                payload["display"] = obj["display"]
        elif event_type == "entity.update":
            payload = {
                "fields": obj.get("p", {}),
            }
            if "ref" in obj:
                payload["ref"] = obj["ref"]
            if "cell_ref" in obj:
                payload["cell_ref"] = obj["cell_ref"]
            if "collection" in obj:
                payload["collection"] = obj["collection"]
        elif event_type == "entity.delete":
            payload = {"ref": obj.get("ref", "")}
        elif event_type == "meta.update":
            # Copy all fields except 't' to payload
            payload = {k: v for k, v in obj.items() if k != "t"}
        elif event_type == "field.add":
            payload = {
                "collection": obj.get("collection", ""),
                "name": obj.get("field", obj.get("name", "")),
                "type": obj.get("type", "string"),
            }
            if "default" in obj:
                payload["default"] = obj["default"]
        elif event_type == "grid.create":
            payload = {
                "collection": obj.get("collection", ""),
                "rows": obj.get("rows", 10),
                "cols": obj.get("cols", 10),
            }
            if "defaults" in obj:
                payload["defaults"] = obj["defaults"]
        else:
            # Generic fallback: use 'p' as payload if present
            payload = obj.get("p", {})
            for k, v in obj.items():
                if k not in ("t", "p"):
                    payload[k] = v

        return {"type": event_type, "payload": payload}

    def _build_user_message(self, message: str, snapshot: dict[str, Any], recent_events: list[Event]) -> str:
        """Build user message with snapshot and event context."""
        # Serialize snapshot
        snapshot_json = json.dumps(snapshot, indent=2)

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

Return JSONL (one JSON object per line). End with a voice line for the response.
"""


# Singleton instance
l3_synthesizer = L3Synthesizer()
