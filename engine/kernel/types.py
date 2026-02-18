"""
AIde Kernel — Shared Types (v3 Unified Entity Model)

Data classes used across primitives, reducer, renderer, and assembly.
These are the contracts that bind the kernel together.

v3 key changes:
- `schemas` container replaces `collections` — stores TypeScript interfaces + render templates
- `entities` are top-level with `_schema` reference (not nested in collections)
- `Record<string, T>` for typed child collections (nested entities)
- `_pos` for fractional indexing (ordering)
- `_shape` for grid layout (e.g., [8, 8] for chessboard, [10, 10] for football squares)
- Primitives: schema.create/update/remove, entity.create/update/remove
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# v3: entity paths use slash-separated segments, each a valid ID
PATH_SEGMENT_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


# ---------------------------------------------------------------------------
# Primitive type registry
# ---------------------------------------------------------------------------

PRIMITIVE_TYPES: set[str] = {
    # Schema (v3)
    "schema.create",
    "schema.update",
    "schema.remove",
    # Entity (v3)
    "entity.create",
    "entity.update",
    "entity.remove",
    # Block (layout)
    "block.set",
    "block.remove",
    "block.reorder",
    # Style
    "style.set",
    # Meta
    "meta.update",
    "meta.annotate",
}

BLOCK_TYPES: set[str] = {
    "root",
    "heading",
    "text",
    "metric",
    "entity_view",
    "divider",
    "image",
    "callout",
    "column_list",
    "column",
}

# Known style tokens and their defaults
DEFAULT_STYLES: dict[str, str] = {
    "primary_color": "#2d3748",
    "bg_color": "#fafaf9",
    "text_color": "#1a1a1a",
    "font_family": "Inter",
    "heading_font": "Cormorant Garamond",
    "density": "comfortable",
}

DENSITY_VALUES: set[str] = {"compact", "comfortable", "spacious"}

# Known meta properties
KNOWN_META_PROPERTIES: set[str] = {"title", "identity", "visibility", "archived"}

# Escalation reasons
ESCALATION_REASONS: set[str] = {
    "no_schema",
    "unknown_entity",
    "unknown_field",
    "novel_view",
    "structural_change",
    "ambiguous",
    "complex_conditional",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    """
    The aide's current state — v3 Unified Entity Model.

    v3 structure:
    - schemas: dict[schema_id, schema_def] — TypeScript interfaces + render templates
    - entities: dict[entity_id, entity_data] — top-level entities with _schema references
    - blocks: dict[block_id, block_def] — layout blocks
    - styles: dict — global style tokens
    - meta: dict — metadata (title, identity, visibility)
    - annotations: list — pinned notes
    """

    version: int = 3
    meta: dict[str, Any] = field(default_factory=dict)
    schemas: dict[str, Any] = field(default_factory=dict)
    entities: dict[str, Any] = field(default_factory=dict)
    blocks: dict[str, Any] = field(default_factory=lambda: {"block_root": {"type": "root", "children": []}})
    styles: dict[str, Any] = field(default_factory=dict)
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "meta": self.meta,
            "schemas": self.schemas,
            "entities": self.entities,
            "blocks": self.blocks,
            "styles": self.styles,
            "annotations": self.annotations,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Snapshot:
        return cls(
            version=d.get("version", 3),
            meta=d.get("meta", {}),
            schemas=d.get("schemas", {}),
            entities=d.get("entities", {}),
            blocks=d.get("blocks", {"block_root": {"type": "root", "children": []}}),
            styles=d.get("styles", {}),
            annotations=d.get("annotations", []),
        )


@dataclass
class Event:
    """
    Wraps a primitive with metadata for the append-only event log.
    The reducer reads only `type` and `payload`.
    """

    id: str
    sequence: int
    timestamp: str  # ISO 8601 UTC
    actor: str
    source: str
    type: str
    payload: dict[str, Any]
    intent: str | None = None
    message: str | None = None
    message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
        }
        if self.intent is not None:
            d["intent"] = self.intent
        if self.message is not None:
            d["message"] = self.message
        if self.message_id is not None:
            d["message_id"] = self.message_id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Event:
        return cls(
            id=d["id"],
            sequence=d["sequence"],
            timestamp=d["timestamp"],
            actor=d["actor"],
            source=d["source"],
            type=d["type"],
            payload=d["payload"],
            intent=d.get("intent"),
            message=d.get("message"),
            message_id=d.get("message_id"),
        )


@dataclass
class Warning:
    """A non-fatal issue encountered during reduction."""

    code: str
    message: str
    details: dict[str, Any] | None = None


@dataclass
class ReduceResult:
    """
    Result of applying one event to a snapshot.
    The reducer never throws — it always returns one of these.
    """

    snapshot: dict[str, Any]  # AideState
    applied: bool
    warnings: list[Warning] = field(default_factory=list)
    error: str | None = None


@dataclass
class Blueprint:
    """
    The aide's DNA — identity, voice rules, and LLM system prompt.
    Embedded in the HTML file for portability.
    """

    identity: str
    voice: str = "No first person. State reflections only."
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "voice": self.voice,
            "prompt": self.prompt,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Blueprint:
        return cls(
            identity=d.get("identity", ""),
            voice=d.get("voice", "No first person. State reflections only."),
            prompt=d.get("prompt", ""),
        )


@dataclass
class RenderOptions:
    """Options controlling what the renderer includes in output."""

    include_events: bool = True
    include_blueprint: bool = True
    include_fonts: bool = True
    footer: str | None = None  # "Made with AIde" for free tier
    base_url: str = "https://toaide.com"
    channel: str = "html"  # "html" or "text"


@dataclass
class AideFile:
    """In-memory representation of a loaded aide HTML file."""

    aide_id: str
    snapshot: dict[str, Any]  # AideState
    events: list[Event]
    blueprint: Blueprint
    html: str
    last_sequence: int
    size_bytes: int
    loaded_from: str  # "r2" or "new"


@dataclass
class ApplyResult:
    """Result of applying a batch of events through the assembly layer."""

    aide_file: AideFile
    applied: list[Event]
    rejected: list[tuple[Event, str]]  # (event, error_reason)
    warnings: list[Warning]


@dataclass
class ParsedAide:
    """Result of parsing an existing aide HTML file."""

    blueprint: Blueprint | None
    snapshot: dict[str, Any] | None
    events: list[Event]
    parse_errors: list[str]


@dataclass
class Escalation:
    """Signal from L2 when it can't compile a user message into primitives."""

    reason: str
    user_message: str
    context: str
    attempted: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "escalation",
            "reason": self.reason,
            "user_message": self.user_message,
            "context": self.context,
            "attempted": self.attempted,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_valid_id(value: str) -> bool:
    """Check if a string is a valid AIde ID (snake_case, max 64 chars)."""
    return bool(ID_PATTERN.match(value))


def parse_entity_path(path: str) -> list[str]:
    """
    Parse an entity path into segments.

    Examples:
      "grocery_list"                   → ["grocery_list"]
      "grocery_list/items/item_milk"  → ["grocery_list", "items", "item_milk"]
      "poker_league/players/player_mike" → ["poker_league", "players", "player_mike"]

    Returns empty list if path is invalid.
    """
    segments = path.split("/")
    for seg in segments:
        if not PATH_SEGMENT_PATTERN.match(seg):
            return []
    return segments


def is_valid_entity_path(path: str) -> bool:
    """Return True if path is a valid entity path (1+ slash-separated IDs)."""
    return len(parse_entity_path(path)) > 0


def now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
