"""
AIde Kernel — Assembly Layer

Sits between the pure functions (reducer, renderer) and the outside world
(R2 storage, the orchestrator). Coordinates the lifecycle of an aide's HTML file.

Operations: load, apply, save, create, publish, fork

This is where IO happens. The reducer and renderer are pure.

Reference: aide_assembly_spec.md
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
import uuid
from typing import Any

from engine.kernel.types import (
    AideFile,
    ApplyResult,
    Blueprint,
    Event,
    ParsedAide,
    ReduceResult,
    RenderOptions,
    Warning,
    now_iso,
)
from engine.kernel.primitives import validate_primitive
from engine.kernel.reducer import reduce, empty_state
from engine.kernel.renderer import render


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AideNotFound(Exception):
    """Aide does not exist in storage."""
    pass


class ParseError(Exception):
    """HTML file exists but embedded JSON is malformed."""
    pass


class VersionNotSupported(Exception):
    """Snapshot version is from a future format."""
    pass


# ---------------------------------------------------------------------------
# Storage protocol
# ---------------------------------------------------------------------------

class AideStorage:
    """
    Abstract storage interface.
    Implement with R2 for production, or in-memory for tests.
    """

    async def get(self, aide_id: str) -> str | None:
        """Fetch HTML file for an aide. Returns None if not found."""
        raise NotImplementedError

    async def put(self, aide_id: str, html: str) -> None:
        """Write HTML file for an aide (workspace bucket)."""
        raise NotImplementedError

    async def put_published(self, slug: str, html: str) -> None:
        """Write HTML file to published bucket."""
        raise NotImplementedError

    async def delete(self, aide_id: str) -> None:
        """Delete an aide's files from both buckets."""
        raise NotImplementedError


class MemoryStorage(AideStorage):
    """In-memory storage for testing."""

    def __init__(self) -> None:
        self.workspace: dict[str, str] = {}
        self.published: dict[str, str] = {}

    async def get(self, aide_id: str) -> str | None:
        return self.workspace.get(aide_id)

    async def put(self, aide_id: str, html: str) -> None:
        self.workspace[aide_id] = html

    async def put_published(self, slug: str, html: str) -> None:
        self.published[slug] = html

    async def delete(self, aide_id: str) -> None:
        self.workspace.pop(aide_id, None)


# ---------------------------------------------------------------------------
# HTML Parsing
# ---------------------------------------------------------------------------

def parse_aide_html(html: str) -> ParsedAide:
    """
    Extract blueprint, snapshot, and events from an aide HTML file.
    Uses regex on script tags — simple, no external dependency.
    """
    errors: list[str] = []
    blueprint: Blueprint | None = None
    snapshot: dict[str, Any] | None = None
    events: list[Event] = []

    # Extract blueprint
    bp_match = re.search(
        r'<script[^>]*id="aide-blueprint"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if bp_match:
        try:
            bp_data = json.loads(bp_match.group(1).strip())
            blueprint = Blueprint.from_dict(bp_data)
        except (json.JSONDecodeError, KeyError) as e:
            errors.append(f"Failed to parse blueprint: {e}")

    # Extract snapshot
    state_match = re.search(
        r'<script[^>]*id="aide-state"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if state_match:
        try:
            snapshot = json.loads(state_match.group(1).strip())
        except json.JSONDecodeError as e:
            errors.append(f"Failed to parse snapshot: {e}")

    # Extract events
    events_match = re.search(
        r'<script[^>]*id="aide-events"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if events_match:
        try:
            events_data = json.loads(events_match.group(1).strip())
            events = [Event.from_dict(e) for e in events_data]
        except (json.JSONDecodeError, KeyError) as e:
            errors.append(f"Failed to parse events: {e}")

    return ParsedAide(
        blueprint=blueprint,
        snapshot=snapshot,
        events=events,
        parse_errors=errors,
    )


# ---------------------------------------------------------------------------
# Assembly class
# ---------------------------------------------------------------------------

class AideAssembly:
    """
    Manages the lifecycle of an aide's HTML file.
    Coordinates reducer + renderer + storage.
    """

    def __init__(self, storage: AideStorage):
        self._storage = storage
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, aide_id: str) -> asyncio.Lock:
        """Per-aide asyncio lock for single-instance serialization (v1)."""
        if aide_id not in self._locks:
            self._locks[aide_id] = asyncio.Lock()
        return self._locks[aide_id]

    # -- load --

    async def load(self, aide_id: str) -> AideFile:
        """
        Read an aide from R2.
        Fetches HTML, parses embedded JSON, returns AideFile.
        """
        html = await self._storage.get(aide_id)
        if html is None:
            raise AideNotFound(aide_id)

        parsed = parse_aide_html(html)
        if parsed.parse_errors:
            raise ParseError(f"Failed to parse aide {aide_id}: {parsed.parse_errors}")

        snapshot = parsed.snapshot or empty_state()
        events = parsed.events
        blueprint = parsed.blueprint or Blueprint(identity="")

        version = snapshot.get("version", 1)
        if version > 1:
            raise VersionNotSupported(f"Snapshot version {version} not supported")

        last_seq = max((e.sequence for e in events), default=0)

        return AideFile(
            aide_id=aide_id,
            snapshot=snapshot,
            events=events,
            blueprint=blueprint,
            html=html,
            last_sequence=last_seq,
            size_bytes=len(html.encode("utf-8")),
            loaded_from="r2",
        )

    # -- apply --

    async def apply(
        self,
        aide_file: AideFile,
        events: list[Event],
    ) -> ApplyResult:
        """
        Validate → reduce → re-render.
        Updates the AideFile in-memory. Call save() to persist.

        Partial application: rejected events are skipped, the rest still apply.
        """
        applied: list[Event] = []
        rejected: list[tuple[Event, str]] = []
        all_warnings: list[Warning] = []
        snapshot = aide_file.snapshot
        seq = aide_file.last_sequence

        for event in events:
            # Assign sequence if not already set
            if event.sequence == 0:
                seq += 1
                event.sequence = seq
                event.id = f"evt_{event.timestamp[:10].replace('-', '')}_{seq:03d}"

            # 1. Structural validation
            validation_errors = validate_primitive(event.type, event.payload)
            if validation_errors:
                rejected.append((event, "; ".join(validation_errors)))
                continue

            # 2. Reduce
            result: ReduceResult = reduce(snapshot, event)
            if not result.applied:
                rejected.append((event, result.error or "Unknown error"))
                continue

            # Applied
            snapshot = result.snapshot
            all_warnings.extend(result.warnings)
            applied.append(event)
            aide_file.events.append(event)

        aide_file.snapshot = snapshot
        aide_file.last_sequence = seq

        # Re-render if anything changed
        if applied:
            aide_file.html = render(
                snapshot,
                aide_file.blueprint,
                aide_file.events,
            )
            aide_file.size_bytes = len(aide_file.html.encode("utf-8"))

        return ApplyResult(
            aide_file=aide_file,
            applied=applied,
            rejected=rejected,
            warnings=all_warnings,
        )

    # -- save --

    async def save(self, aide_file: AideFile) -> None:
        """Write an aide back to R2 workspace bucket."""
        try:
            await self._storage.put(aide_file.aide_id, aide_file.html)
        except Exception:
            # Retry once per spec
            await self._storage.put(aide_file.aide_id, aide_file.html)

    # -- create --

    async def create(self, blueprint: Blueprint) -> AideFile:
        """
        Initialize a new aide with empty state.
        Does NOT save — caller persists after first L3 events.
        """
        aide_id = str(uuid.uuid4())
        snapshot = empty_state()

        # Title from first sentence of identity
        identity = blueprint.identity
        if identity:
            title = identity.split(".")[0].strip()[:100]
            snapshot["meta"]["title"] = title

        html = render(snapshot, blueprint, events=[])

        return AideFile(
            aide_id=aide_id,
            snapshot=snapshot,
            events=[],
            blueprint=blueprint,
            html=html,
            last_sequence=0,
            size_bytes=len(html.encode("utf-8")),
            loaded_from="new",
        )

    # -- publish --

    async def publish(
        self,
        aide_file: AideFile,
        *,
        slug: str | None = None,
        is_free_tier: bool = True,
    ) -> str:
        """
        Copy workspace file to published bucket.
        Returns the published URL.
        """
        if slug is None:
            slug = uuid.uuid4().hex[:8]

        footer = "Made with AIde" if is_free_tier else None
        options = RenderOptions(
            include_events=len(aide_file.events) <= 500,
            include_blueprint=True,
            footer=footer,
        )

        published_html = render(
            aide_file.snapshot,
            aide_file.blueprint,
            aide_file.events if options.include_events else None,
            options,
        )

        await self._storage.put_published(slug, published_html)
        return f"https://toaide.com/p/{slug}"

    # -- fork --

    async def fork(self, aide_id: str) -> AideFile:
        """
        Deep clone an aide's state and blueprint.
        Clears events, annotations, sequence metadata.
        Returns unsaved AideFile.
        """
        source = await self.load(aide_id)
        new_id = str(uuid.uuid4())
        snapshot = copy.deepcopy(source.snapshot)

        # Strip sequence metadata from entities
        for coll in snapshot.get("collections", {}).values():
            for entity in coll.get("entities", {}).values():
                entity.pop("_created_seq", None)
                entity.pop("_updated_seq", None)
                entity.pop("_removed_seq", None)

        # Update meta
        old_title = snapshot.get("meta", {}).get("title", "")
        if old_title:
            snapshot["meta"]["title"] = f"Copy of {old_title}"

        snapshot["annotations"] = []

        html = render(snapshot, source.blueprint, events=[])

        return AideFile(
            aide_id=new_id,
            snapshot=snapshot,
            events=[],
            blueprint=copy.deepcopy(source.blueprint),
            html=html,
            last_sequence=0,
            size_bytes=len(html.encode("utf-8")),
            loaded_from="new",
        )

    # -- integrity --

    async def integrity_check(self, aide_file: AideFile) -> tuple[bool, list[str]]:
        """Verify snapshot matches event replay."""
        from engine.kernel.reducer import replay

        replayed = replay(aide_file.events)
        stored = copy.deepcopy(aide_file.snapshot)
        stored.pop("version", None)
        replayed.pop("version", None)

        if json.dumps(stored, sort_keys=True) == json.dumps(replayed, sort_keys=True):
            return True, []
        return False, ["Snapshot does not match event replay"]

    async def repair(self, aide_file: AideFile) -> AideFile:
        """Rebuild snapshot from events, re-render HTML."""
        from engine.kernel.reducer import replay

        aide_file.snapshot = replay(aide_file.events)
        aide_file.snapshot["version"] = 1
        aide_file.html = render(aide_file.snapshot, aide_file.blueprint, aide_file.events)
        aide_file.size_bytes = len(aide_file.html.encode("utf-8"))
        return aide_file

    # -- compaction --

    async def compact(self, aide_file: AideFile, keep_recent: int = 50) -> AideFile:
        """
        Compact the event log. Keeps the most recent N events.
        Snapshot already reflects all events, so old events are redundant.
        """
        if len(aide_file.events) <= keep_recent:
            return aide_file

        aide_file.events = aide_file.events[-keep_recent:]
        aide_file.html = render(
            aide_file.snapshot,
            aide_file.blueprint,
            aide_file.events,
        )
        aide_file.size_bytes = len(aide_file.html.encode("utf-8"))
        return aide_file
