"""Main orchestrator — coordinates L2/L3, reducer, renderer, and persistence."""

import uuid
from datetime import UTC, datetime
from typing import Any

from backend.repos.aide_repo import aide_repo
from backend.repos.conversation_repo import conversation_repo
from backend.services.l2_compiler import l2_compiler
from backend.services.l3_synthesizer import l3_synthesizer
from backend.services.r2 import r2_service
from engine.kernel.reducer import reduce
from engine.kernel.renderer import render
from engine.kernel.types import Event, ReduceResult, Snapshot


class Orchestrator:
    """Main AI orchestration coordinator."""

    async def process_message(
        self,
        aide_id: str,
        user_id: str,
        message: str,
        source: str = "web",
        image_data: bytes | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and update aide state.

        Args:
            aide_id: Aide ID
            user_id: User ID
            message: User message text
            source: Message source ("web", "signal", "telegram")
            image_data: Optional image bytes

        Returns:
            Dict with:
            - response: response text to show user
            - html_url: URL to rendered HTML
            - primitives_count: number of primitives applied
        """
        # 1. Load current aide state from DB
        aide = await aide_repo.get(aide_id, user_id)
        if not aide:
            raise ValueError(f"Aide {aide_id} not found")

        # Parse state JSON
        snapshot = self._parse_snapshot(aide.state)

        # Load recent events from conversation
        conversation = await conversation_repo.get_or_create(aide_id, user_id)
        recent_events = self._load_recent_events(conversation["messages"])

        # 2. Route to L2 or L3
        primitives: list[dict[str, Any]] = []
        response_text = ""

        # Check if image input or empty snapshot → route to L3
        if image_data or not snapshot.collections:
            # Route to L3 (Sonnet)
            l3_result = await l3_synthesizer.synthesize(message, snapshot, recent_events, image_data)
            primitives = l3_result["primitives"]
            response_text = l3_result["response"]
        else:
            # Route to L2 (Haiku) first
            l2_result = await l2_compiler.compile(message, snapshot, recent_events)

            if l2_result["escalate"]:
                # L2 requested escalation → route to L3
                l3_result = await l3_synthesizer.synthesize(message, snapshot, recent_events)
                primitives = l3_result["primitives"]
                response_text = l3_result["response"]
            else:
                primitives = l2_result["primitives"]
                response_text = l2_result["response"]

        # 3. Apply primitives through reducer
        events = self._wrap_primitives(primitives, user_id, source, message)
        new_snapshot = snapshot

        for event in events:
            result: ReduceResult = reduce(new_snapshot, event)
            if result.error:
                print(f"Reducer error: {result.error}")
                # Skip invalid event, continue with others
                continue
            new_snapshot = result.snapshot

        # 4. Render HTML
        html_content = render(new_snapshot, blueprint={}, events=events)

        # 5. Save state to DB
        await aide_repo.update_state(aide_id, user_id, self._serialize_snapshot(new_snapshot))

        # 6. Upload HTML to R2
        r2_key = await r2_service.upload_html(aide_id, html_content)

        # 7. Save message to conversation
        await conversation_repo.add_message(
            conversation_id=conversation["id"],
            user_id=user_id,
            role="user",
            content=message,
        )

        if response_text:
            await conversation_repo.add_message(
                conversation_id=conversation["id"],
                user_id=user_id,
                role="assistant",
                content=response_text,
            )

        return {
            "response": response_text,
            "html_url": f"https://r2.toaide.com/{r2_key}",
            "primitives_count": len(primitives),
        }

    def _parse_snapshot(self, state_json: dict[str, Any]) -> Snapshot:
        """Parse snapshot from DB JSON."""
        return Snapshot(
            collections=state_json.get("collections", {}),
            entities=state_json.get("entities", {}),
            blocks=state_json.get("blocks", []),
            views=state_json.get("views", {}),
            styles=state_json.get("styles", {}),
            meta=state_json.get("meta", {}),
            relationships=state_json.get("relationships", []),
        )

    def _serialize_snapshot(self, snapshot: Snapshot) -> dict[str, Any]:
        """Serialize snapshot to DB JSON."""
        return {
            "collections": snapshot.collections,
            "entities": snapshot.entities,
            "blocks": snapshot.blocks,
            "views": snapshot.views,
            "styles": snapshot.styles,
            "meta": snapshot.meta,
            "relationships": snapshot.relationships,
        }

    def _load_recent_events(self, messages: list[dict[str, Any]]) -> list[Event]:
        """Load recent events from conversation messages."""
        events: list[Event] = []

        # Extract events from assistant messages (they contain primitives metadata)
        for msg in messages[-20:]:  # Last 20 messages
            if msg.get("role") == "assistant" and msg.get("metadata"):
                metadata = msg["metadata"]
                if "primitives" in metadata:
                    for primitive in metadata["primitives"]:
                        events.append(
                            Event(
                                id=f"evt_{uuid.uuid4().hex[:8]}",
                                sequence=len(events),
                                timestamp=msg.get("created_at", datetime.now(UTC).isoformat()),
                                actor=msg.get("user_id", "system"),
                                source="web",
                                type=primitive["type"],
                                payload=primitive["payload"],
                            )
                        )

        return events

    def _wrap_primitives(
        self,
        primitives: list[dict[str, Any]],
        user_id: str,
        source: str,
        message: str,
    ) -> list[Event]:
        """Wrap primitives in event metadata."""
        events: list[Event] = []
        timestamp = datetime.now(UTC).isoformat()

        for i, primitive in enumerate(primitives):
            events.append(
                Event(
                    id=f"evt_{uuid.uuid4().hex[:8]}",
                    sequence=i,
                    timestamp=timestamp,
                    actor=user_id,
                    source=source,
                    type=primitive["type"],
                    payload=primitive["payload"],
                    message=message,
                )
            )

        return events


# Singleton instance
orchestrator = Orchestrator()
