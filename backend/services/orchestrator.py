"""Main orchestrator — coordinates L2/L3, reducer, renderer, and persistence."""

import time
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.config import settings
from backend.models.conversation import Message
from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.services.flight_recorder import FlightRecorder
from backend.services.flight_recorder_uploader import flight_recorder_uploader
from backend.services.grid_resolver import resolve_primitives
from backend.services.l2_compiler import l2_compiler
from backend.services.l3_synthesizer import l3_synthesizer
from backend.services.r2 import r2_service
from engine.kernel.reducer_v2 import empty_snapshot as empty_v2_snapshot, reduce
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
        snapshot_before = snapshot.to_dict()

        # Load or create conversation for this aide
        conversation = await self.conv_repo.get_for_aide(user_id, aide_id)
        if not conversation:
            conversation = await self.conv_repo.create(user_id, aide_id, channel=source)

        # Load recent events from conversation messages
        recent_events = self._load_recent_events(conversation.messages)

        # 2. Set up flight recorder for this turn
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id=turn_id,
            aide_id=str(aide_id),
            user_id=str(user_id),
            source=source,
            user_message=message,
            snapshot_before=snapshot_before,
        )

        # 3. Route to L2 or L3
        primitives: list[dict[str, Any]] = []
        response_text = ""

        try:
            # Check if image input or empty snapshot → route to L3
            if image_data or not snapshot.collections:
                # Route to L3 (production model)
                print(f"Routing to L3 (image={bool(image_data)}, empty_snapshot={not snapshot.collections})")
                l3_result = await self._call_l3(
                    recorder=recorder,
                    message=message,
                    snapshot=snapshot,
                    recent_events=recent_events,
                    image_data=image_data,
                    shadow=False,
                )
                primitives = l3_result["primitives"]
                response_text = l3_result["response"]

                # Shadow L3 call (sequential, non-blocking to user)
                await self._call_l3_shadow(
                    recorder=recorder,
                    message=message,
                    snapshot=snapshot,
                    recent_events=recent_events,
                    image_data=image_data,
                )
            else:
                # Route to L2 (production model) first
                print("Routing to L2 first")
                l2_result = await self._call_l2(
                    recorder=recorder,
                    message=message,
                    snapshot=snapshot,
                    recent_events=recent_events,
                    shadow=False,
                )

                if l2_result["escalate"]:
                    # L2 requested escalation → route to L3
                    print("L2 escalated to L3")
                    l3_result = await self._call_l3(
                        recorder=recorder,
                        message=message,
                        snapshot=snapshot,
                        recent_events=recent_events,
                        image_data=None,
                        shadow=False,
                    )
                    primitives = l3_result["primitives"]
                    response_text = l3_result["response"]

                    # Shadow L3 call
                    await self._call_l3_shadow(
                        recorder=recorder,
                        message=message,
                        snapshot=snapshot,
                        recent_events=recent_events,
                        image_data=None,
                    )
                else:
                    print(f"L2 handled: {len(l2_result['primitives'])} primitives")
                    primitives = l2_result["primitives"]
                    response_text = l2_result["response"]

                    # Shadow L2 call
                    await self._call_l2_shadow(
                        recorder=recorder,
                        message=message,
                        snapshot=snapshot,
                        recent_events=recent_events,
                    )
        except Exception as e:
            # AI call failed even after retries — record failed turn and return error
            print(f"AI routing failed: {e}")
            error_response = "Something went wrong processing that message. Please try again."

            # Save messages to conversation even on failure
            user_msg = Message(role="user", content=message, timestamp=datetime.now(UTC))
            await self.conv_repo.append_message(user_id, conversation.id, user_msg)
            assistant_msg = Message(
                role="assistant",
                content=error_response,
                timestamp=datetime.now(UTC),
                metadata={"error": str(e)},
            )
            await self.conv_repo.append_message(user_id, conversation.id, assistant_msg)

            turn_record = recorder.end_turn(
                snapshot_after=snapshot_before,  # No change on failure
                primitives_emitted=[],
                primitives_applied=0,
                response_text=error_response,
                error=str(e),
            )
            flight_recorder_uploader.enqueue(turn_record)
            return {
                "response": error_response,
                "html_url": f"/api/aides/{aide_id}/preview",
                "primitives_count": 0,
                "error": True,
            }

        # 3.5. Resolve any grid cell references in primitives
        snapshot_dict = snapshot.to_dict()
        resolve_result = resolve_primitives(primitives, snapshot_dict)
        if resolve_result.error:
            # Grid resolution failed — record failed turn and return error
            print(f"Grid resolution error: {resolve_result.error}")

            # Save messages to conversation even on failure
            user_msg = Message(role="user", content=message, timestamp=datetime.now(UTC))
            await self.conv_repo.append_message(user_id, conversation.id, user_msg)
            assistant_msg = Message(
                role="assistant",
                content=resolve_result.error,
                timestamp=datetime.now(UTC),
                metadata={"error": resolve_result.error, "primitives": primitives},
            )
            await self.conv_repo.append_message(user_id, conversation.id, assistant_msg)

            turn_record = recorder.end_turn(
                snapshot_after=snapshot_before,  # No change on failure
                primitives_emitted=primitives,
                primitives_applied=0,
                response_text=resolve_result.error,
                error=f"Grid resolution error: {resolve_result.error}",
            )
            flight_recorder_uploader.enqueue(turn_record)
            return {
                "response": resolve_result.error,
                "html_url": f"/api/aides/{aide_id}/preview",
                "primitives_count": 0,
            }
        primitives = resolve_result.primitives
        # If there was a grid query, use that as the response
        if resolve_result.query_response:
            response_text = resolve_result.query_response

        # 4. Apply primitives through v2 reducer
        print(f"Orchestrator: {len(primitives)} primitives from AI")
        for p in primitives:
            print(f"  - {p.get('type')}: {p.get('payload', {}).keys()}")

        # Convert primitives to v2 events and wrap in Event objects for logging
        v2_events = self._primitives_to_v2_events(primitives)
        events = self._wrap_primitives(primitives, str(user_id), source, message)

        # Start with empty v2 snapshot if current one is empty/v1 format
        if not snapshot_dict.get("entities"):
            new_snapshot = empty_v2_snapshot()
            # Copy over meta if present
            if snapshot_dict.get("meta"):
                new_snapshot["meta"] = snapshot_dict["meta"]
        else:
            new_snapshot = snapshot_dict

        applied_count = 0
        for v2_event in v2_events:
            result: ReduceResult = reduce(new_snapshot, v2_event)
            if not result.accepted:
                print(f"Reducer REJECTED {v2_event.get('t')}: {result.reason}")
                # Skip invalid event, continue with others
                continue
            applied_count += 1
            new_snapshot = result.snapshot

        print(f"Orchestrator: {applied_count}/{len(v2_events)} events applied successfully")

        # 5. Render HTML
        blueprint = Blueprint(identity=aide.title if hasattr(aide, "title") else "AIde")
        html_content = render(new_snapshot, blueprint=blueprint, events=events)

        # 6. Save state to DB
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

        # Extract title from meta.update if present
        new_title = new_snapshot.get("meta", {}).get("title")
        await self.aide_repo.update_state(user_id, aide_id, new_snapshot, updated_event_log, title=new_title)

        # 7. Upload HTML to R2 (non-blocking — DB is source of truth)
        try:
            await r2_service.upload_html(str(aide_id), html_content)
        except Exception as e:
            # Log but don't fail — state is saved in DB, R2 is just a cache
            print(f"R2 upload failed (will retry on next message): {e}")

        # 8. Save messages to conversation
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

        # 9. Finalize flight recorder and enqueue for upload
        turn_record = recorder.end_turn(
            snapshot_after=new_snapshot,
            primitives_emitted=primitives,
            primitives_applied=applied_count,
            response_text=response_text,
        )
        flight_recorder_uploader.enqueue(turn_record)

        return {
            "response": response_text,
            "html_url": f"/api/aides/{aide_id}/preview",
            "primitives_count": len(primitives),
        }

    async def _call_l2(
        self,
        recorder: FlightRecorder,
        message: str,
        snapshot: Snapshot,
        recent_events: list[Event],
        shadow: bool,
    ) -> dict[str, Any]:
        """
        Call L2 (Haiku-class) and record result in flight recorder.

        Uses production model (settings.L2_MODEL) when shadow=False,
        shadow model (settings.L2_SHADOW_MODEL) when shadow=True.
        """
        model = settings.L2_SHADOW_MODEL if shadow else settings.L2_MODEL
        start = time.monotonic()
        error: str | None = None
        result: dict[str, Any] = {"primitives": [], "response": "", "escalate": False}
        usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

        # Build the prompt (same format as l2_compiler internal)
        prompt = l2_compiler._build_user_message(message, snapshot, recent_events)

        try:
            # Override model for shadow calls by calling ai_provider directly
            if shadow:
                from backend.services.ai_provider import ai_provider

                raw = await ai_provider.call_claude(
                    model=model,
                    system=l2_compiler.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096,
                    temperature=0.0,
                )
                result = self._parse_l2_response(raw["content"])
                usage = raw["usage"]
            else:
                result = await l2_compiler.compile(message, snapshot, recent_events)
                usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})
        except Exception as e:
            error = str(e)
            print(f"L2 {'shadow' if shadow else 'production'} call failed: {e}")

        latency_ms = int((time.monotonic() - start) * 1000)
        recorder.record_llm_call(
            shadow=shadow,
            model=model,
            tier="L2",
            prompt=prompt,
            response=result.get("_raw_response", ""),
            usage=usage,
            latency_ms=latency_ms,
            error=error,
        )

        return result

    async def _call_l3(
        self,
        recorder: FlightRecorder,
        message: str,
        snapshot: Snapshot,
        recent_events: list[Event],
        image_data: bytes | None,
        shadow: bool,
    ) -> dict[str, Any]:
        """
        Call L3 (Sonnet-class) and record result in flight recorder.

        Uses production model (settings.L3_MODEL) when shadow=False,
        shadow model (settings.L3_SHADOW_MODEL) when shadow=True.
        """
        model = settings.L3_SHADOW_MODEL if shadow else settings.L3_MODEL
        start = time.monotonic()
        error: str | None = None
        result: dict[str, Any] = {"primitives": [], "response": ""}
        usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

        prompt = l3_synthesizer._build_user_message(message, snapshot, recent_events)

        try:
            if shadow:
                from backend.services.ai_provider import ai_provider

                raw = await ai_provider.call_claude(
                    model=model,
                    system=l3_synthesizer.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=16384,
                    temperature=0.0,
                )
                result = self._parse_l3_response(raw["content"])
                usage = raw["usage"]
            else:
                result = await l3_synthesizer.synthesize(message, snapshot, recent_events, image_data=image_data)
                usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})
        except Exception as e:
            error = str(e)
            print(f"L3 {'shadow' if shadow else 'production'} call failed: {e}")

        latency_ms = int((time.monotonic() - start) * 1000)
        recorder.record_llm_call(
            shadow=shadow,
            model=model,
            tier="L3",
            prompt=prompt,
            response=result.get("_raw_response", ""),
            usage=usage,
            latency_ms=latency_ms,
            error=error,
        )

        return result

    async def _call_l2_shadow(
        self,
        recorder: FlightRecorder,
        message: str,
        snapshot: Snapshot,
        recent_events: list[Event],
    ) -> None:
        """Run shadow L2 call. Never raises — failures are logged and recorded."""
        try:
            await self._call_l2(
                recorder=recorder,
                message=message,
                snapshot=snapshot,
                recent_events=recent_events,
                shadow=True,
            )
        except Exception as e:
            print(f"Shadow L2 call error (non-fatal): {e}")

    async def _call_l3_shadow(
        self,
        recorder: FlightRecorder,
        message: str,
        snapshot: Snapshot,
        recent_events: list[Event],
        image_data: bytes | None,
    ) -> None:
        """Run shadow L3 call. Never raises — failures are logged and recorded."""
        try:
            await self._call_l3(
                recorder=recorder,
                message=message,
                snapshot=snapshot,
                recent_events=recent_events,
                image_data=image_data,
                shadow=True,
            )
        except Exception as e:
            print(f"Shadow L3 call error (non-fatal): {e}")

    def _parse_l2_response(self, content: str) -> dict[str, Any]:
        """Parse L2 JSON response (same logic as l2_compiler)."""
        import json

        content = content.strip()
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

        try:
            data = json.loads(content)
            return {
                "primitives": data.get("primitives", []),
                "response": data.get("response", ""),
                "escalate": data.get("escalate", False),
                "_raw_response": content,
            }
        except json.JSONDecodeError:
            return {"primitives": [], "response": "", "escalate": True, "_raw_response": content}

    def _parse_l3_response(self, content: str) -> dict[str, Any]:
        """Parse L3 JSON response (same logic as l3_synthesizer)."""
        import json

        content = content.strip()
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

        try:
            data = json.loads(content)
            return {
                "primitives": data.get("primitives", []),
                "response": data.get("response", ""),
                "_raw_response": content,
            }
        except json.JSONDecodeError:
            return {"primitives": [], "response": "", "_raw_response": content}

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

    def _primitives_to_v2_events(self, primitives: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert v1 primitives (type/payload) to v2 events (t/shorthand)."""
        v2_events = []
        for p in primitives:
            ptype = p.get("type", "")
            payload = p.get("payload", {})

            if ptype == "collection.create":
                # v2 doesn't have collections, convert to entity.create with section display
                v2_events.append({
                    "t": "entity.create",
                    "id": payload.get("id", ""),
                    "parent": "root",
                    "display": "section",
                    "p": {"title": payload.get("name", "")},
                })
            elif ptype == "entity.create":
                # Convert to v2 format
                collection = payload.get("collection", "")
                entity_id = payload.get("id", "")
                fields = payload.get("fields", {})
                display = payload.get("display", "card")
                v2_events.append({
                    "t": "entity.create",
                    "id": entity_id,
                    "parent": collection or "root",
                    "display": display,
                    "p": fields,
                })
            elif ptype == "entity.update":
                v2_events.append({
                    "t": "entity.update",
                    "ref": payload.get("ref", payload.get("id", "")),
                    "p": payload.get("fields", {}),
                })
            elif ptype == "entity.delete":
                v2_events.append({
                    "t": "entity.remove",
                    "id": payload.get("ref", payload.get("id", "")),
                })
            elif ptype == "meta.update":
                v2_events.append({
                    "t": "meta.update",
                    **{k: v for k, v in payload.items()},
                })
            elif ptype == "field.add":
                v2_events.append({
                    "t": "field.add",
                    "collection": payload.get("collection", ""),
                    "field": payload.get("name", ""),
                    "type": payload.get("type", "string"),
                })
            elif ptype == "grid.create":
                v2_events.append({
                    "t": "grid.create",
                    "collection": payload.get("collection", ""),
                    "rows": payload.get("rows", 10),
                    "cols": payload.get("cols", 10),
                })
            else:
                # Generic fallback
                v2_events.append({
                    "t": ptype,
                    **payload,
                })
        return v2_events

    async def replay_turn(
        self,
        turn_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Replay a turn from flight recorder data (dry run - no persistence).

        Uses the snapshot_before and user_message from the recorded turn,
        re-runs the AI calls with current models/prompts, and returns what
        would have happened without saving anything.

        Args:
            turn_data: The recorded turn data from flight recorder

        Returns:
            Dict with:
            - llm_calls: list of LLM call results (production + shadow)
            - primitives: list of primitives that would be emitted
            - response: response text that would be shown
            - route: which tier handled it (L2 or L3)
            - escalated: whether L2 escalated to L3
        """
        # Extract original context from turn data
        snapshot_before = turn_data.get("snapshot_before", {})
        user_message = turn_data.get("user_message", "")
        source = turn_data.get("source", "web")

        # Parse snapshot
        snapshot = Snapshot.from_dict(snapshot_before)

        # Build empty recent events (replay in isolation)
        recent_events: list[Event] = []

        # Set up a recorder to capture LLM calls (but we won't persist it)
        turn_id = f"replay_{uuid.uuid4().hex[:12]}"
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id=turn_id,
            aide_id=turn_data.get("aide_id", ""),
            user_id="replay",
            source=source,
            user_message=user_message,
            snapshot_before=snapshot_before,
        )

        # Route and call models (same logic as process_message)
        primitives: list[dict[str, Any]] = []
        response_text = ""
        route = "L2"
        escalated = False

        try:
            if not snapshot.collections:
                # Route to L3
                route = "L3"
                l3_result = await self._call_l3(
                    recorder=recorder,
                    message=user_message,
                    snapshot=snapshot,
                    recent_events=recent_events,
                    image_data=None,
                    shadow=False,
                )
                primitives = l3_result["primitives"]
                response_text = l3_result["response"]

                # Shadow L3
                await self._call_l3_shadow(
                    recorder=recorder,
                    message=user_message,
                    snapshot=snapshot,
                    recent_events=recent_events,
                    image_data=None,
                )
            else:
                # Route to L2 first
                l2_result = await self._call_l2(
                    recorder=recorder,
                    message=user_message,
                    snapshot=snapshot,
                    recent_events=recent_events,
                    shadow=False,
                )

                if l2_result["escalate"]:
                    escalated = True
                    route = "L3"
                    l3_result = await self._call_l3(
                        recorder=recorder,
                        message=user_message,
                        snapshot=snapshot,
                        recent_events=recent_events,
                        image_data=None,
                        shadow=False,
                    )
                    primitives = l3_result["primitives"]
                    response_text = l3_result["response"]

                    await self._call_l3_shadow(
                        recorder=recorder,
                        message=user_message,
                        snapshot=snapshot,
                        recent_events=recent_events,
                        image_data=None,
                    )
                else:
                    primitives = l2_result["primitives"]
                    response_text = l2_result["response"]

                    await self._call_l2_shadow(
                        recorder=recorder,
                        message=user_message,
                        snapshot=snapshot,
                        recent_events=recent_events,
                    )
        except Exception as e:
            return {
                "error": str(e),
                "llm_calls": self._serialize_llm_calls(recorder._llm_calls),
                "primitives": [],
                "primitives_raw": [],
                "response": "",
                "route": route,
                "escalated": escalated,
                "grid_resolution_error": None,
            }

        # Run grid resolution (same as process_message)
        primitives_raw = primitives  # Keep original for comparison
        grid_resolution_error = None
        resolve_result = resolve_primitives(primitives, snapshot_before)

        if resolve_result.error:
            grid_resolution_error = resolve_result.error
            primitives = []
        else:
            primitives = resolve_result.primitives
            # If there was a grid query, use that as the response
            if resolve_result.query_response:
                response_text = resolve_result.query_response

        # Return the replay results (no persistence)
        return {
            "llm_calls": self._serialize_llm_calls(recorder._llm_calls),
            "primitives": primitives,
            "primitives_raw": primitives_raw,
            "response": response_text,
            "route": route,
            "escalated": escalated,
            "grid_resolution_error": grid_resolution_error,
        }

    def _serialize_llm_calls(self, llm_calls: list) -> list[dict[str, Any]]:
        """Convert LLMCallRecord dataclasses to dicts for JSON serialization."""
        return [
            {
                "call_id": c.call_id,
                "shadow": c.shadow,
                "model": c.model,
                "tier": c.tier,
                "prompt": c.prompt,
                "response": c.response,
                "usage": c.usage,
                "latency_ms": c.latency_ms,
                "error": c.error,
            }
            for c in llm_calls
        ]


# Singleton instance
orchestrator = Orchestrator()
