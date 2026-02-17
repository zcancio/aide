"""Main orchestrator — coordinates L2/L3, reducer, renderer, and persistence."""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.models.conversation import Message
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.services.l2_compiler import l2_compiler
from backend.services.l3_synthesizer import l3_synthesizer
from backend.services.r2 import r2_service
from engine.kernel.reducer import reduce
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, Event, ReduceResult, Snapshot


class Orchestrator:
    """Main AI orchestration coordinator."""

    def __init__(self) -> None:
        """Initialize orchestrator with repo instances."""
        self.aide_repo = AideRepo()
        self.conv_repo = ConversationRepo()

    async def process_message(
        self,
        user_id: UUID,
        aide_id: UUID,
        message: str,
        source: str = "web",
        image_data: bytes | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and update aide state.

        Args:
            user_id: User UUID
            aide_id: Aide UUID
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
        aide = await self.aide_repo.get(user_id, aide_id)
        if not aide:
            raise ValueError(f"Aide {aide_id} not found")

        # Parse state JSON
        snapshot = self._parse_snapshot(aide.state)

        # Load or create conversation for this aide
        conversation = await self.conv_repo.get_for_aide(user_id, aide_id)
        if not conversation:
            conversation = await self.conv_repo.create(user_id, aide_id, channel=source)

        # Load recent events from conversation messages
        recent_events = self._load_recent_events(conversation.messages)

        # 2. Route to L2 or L3
        primitives: list[dict[str, Any]] = []
        response_text = ""

        # Check if image input or empty snapshot → route to L3
        if image_data or not snapshot.collections:
            # Route to L3 (Sonnet)
            l3_result = await l3_synthesizer.synthesize(message, snapshot, recent_events, image_data=image_data)
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
        events = self._wrap_primitives(primitives, str(user_id), source, message)
        # Convert Snapshot to dict for reducer (which expects dict-style access)
        new_snapshot = snapshot.to_dict()

        for event in events:
            result: ReduceResult = reduce(new_snapshot, event)
            if result.error:
                print(f"Reducer error: {result.error}")
                # Skip invalid event, continue with others
                continue
            new_snapshot = result.snapshot

        # 4. Render HTML
        blueprint = Blueprint(identity=aide.title if hasattr(aide, "title") else "AIde")
        html_content = render(new_snapshot, blueprint=blueprint, events=events)

        # 5. Save state to DB
        serialized_events = [
            {
                "id": e.id,
                "sequence": e.sequence,
                "timestamp": e.timestamp,
                "actor": e.actor,
                "source": e.source,
                "type": e.type,
                "payload": e.payload,
            }
            for e in events
        ]
        updated_event_log = (aide.event_log or []) + serialized_events
        await self.aide_repo.update_state(user_id, aide_id, new_snapshot, updated_event_log)

        # 6. Upload HTML to R2
        r2_key = await r2_service.upload_html(str(aide_id), html_content)

        # 7. Save messages to conversation
        user_message = Message(
            role="user",
            content=message,
            timestamp=datetime.now(UTC),
        )
        await self.conv_repo.append_message(user_id, conversation.id, user_message)

        if response_text:
            assistant_message = Message(
                role="assistant",
                content=response_text,
                timestamp=datetime.now(UTC),
                metadata={"primitives": primitives},
            )
            await self.conv_repo.append_message(user_id, conversation.id, assistant_message)

        return {
            "response": response_text,
            "html_url": f"https://r2.toaide.com/{r2_key}",
            "primitives_count": len(primitives),
        }

    def _parse_snapshot(self, state_json: dict[str, Any]) -> Snapshot:
        """Parse snapshot from DB JSON."""
        return Snapshot.from_dict(state_json)

    def _serialize_snapshot(self, snapshot: Snapshot) -> dict[str, Any]:
        """Serialize snapshot to DB JSON."""
        return snapshot.to_dict()

    def _load_recent_events(self, messages: list[Message]) -> list[Event]:
        """Load recent events from conversation messages."""
        events: list[Event] = []

        # Extract events from assistant messages (they contain primitives metadata)
        for msg in messages[-20:]:  # Last 20 messages
            if msg.role == "assistant" and msg.metadata:
                if "primitives" in msg.metadata:
                    for primitive in msg.metadata["primitives"]:
                        events.append(
                            Event(
                                id=f"evt_{uuid.uuid4().hex[:8]}",
                                sequence=len(events),
                                timestamp=msg.timestamp.isoformat(),
                                actor="assistant",
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
