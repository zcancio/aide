"""
AIde Kernel — Shared Types

Data classes used across primitives, reducer, renderer, and assembly.
These are the contracts that bind the kernel together.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns (from aide_primitive_schemas.md)
# ---------------------------------------------------------------------------

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REF_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}/[a-z][a-z0-9_]{0,63}$")


# ---------------------------------------------------------------------------
# Primitive type registry
# ---------------------------------------------------------------------------

PRIMITIVE_TYPES: set[str] = {
    # Entity (1-3)
    "entity.create",
    "entity.update",
    "entity.remove",
    # Collection (4-6)
    "collection.create",
    "collection.update",
    "collection.remove",
    # Field (7-9)
    "field.add",
    "field.update",
    "field.remove",
    # Relationship (10-11)
    "relationship.set",
    "relationship.constrain",
    # Block (12-14)
    "block.set",
    "block.remove",
    "block.reorder",
    # View (15-17)
    "view.create",
    "view.update",
    "view.remove",
    # Style (18-19)
    "style.set",
    "style.set_entity",
    # Meta (20-22)
    "meta.update",
    "meta.annotate",
    "meta.constrain",
}

BLOCK_TYPES: set[str] = {
    "root",
    "heading",
    "text",
    "metric",
    "collection_view",
    "divider",
    "image",
    "callout",
    "column_list",
    "column",
}

VIEW_TYPES: set[str] = {
    "list",
    "table",
    "grid",
}

# Field types — simple string types and their nullable variants
SIMPLE_FIELD_TYPES: set[str] = {
    "string",
    "string?",
    "int",
    "int?",
    "float",
    "float?",
    "bool",
    "date",
    "date?",
    "datetime",
    "datetime?",
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

# Constraint rule types
CONSTRAINT_RULES: set[str] = {
    "exclude_pair",
    "require_same",
    "max_per_target",
    "min_per_target",
    "collection_max_entities",
    "collection_min_entities",
    "unique_field",
    "required_fields",
}

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
    The aide's current state — all collections, entities, blocks, views, and styles.
    This is what gets persisted to the database and used for rendering.
    """

    collections: dict[str, Any] = field(default_factory=dict)
    entities: dict[str, Any] = field(default_factory=dict)
    blocks: dict[str, Any] = field(default_factory=dict)  # Dict keyed by block_id
    views: dict[str, Any] = field(default_factory=dict)
    styles: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collections": self.collections,
            "entities": self.entities,
            "blocks": self.blocks,
            "views": self.views,
            "styles": self.styles,
            "meta": self.meta,
            "relationships": self.relationships,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Snapshot:
        return cls(
            collections=d.get("collections", {}),
            entities=d.get("entities", {}),
            blocks=d.get("blocks", {}),
            views=d.get("views", {}),
            styles=d.get("styles", {}),
            meta=d.get("meta", {}),
            relationships=d.get("relationships", []),
            constraints=d.get("constraints", []),
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


def parse_ref(ref: str) -> tuple[str, str]:
    """Parse 'collection_id/entity_id' into (collection_id, entity_id)."""
    parts = ref.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid ref format: {ref}")
    return parts[0], parts[1]


def is_valid_id(value: str) -> bool:
    """Check if a string is a valid AIde ID (snake_case, max 64 chars)."""
    return bool(ID_PATTERN.match(value))


def is_valid_ref(value: str) -> bool:
    """Check if a string is a valid entity ref (collection_id/entity_id)."""
    return bool(REF_PATTERN.match(value))


def is_nullable_type(field_type: str | dict) -> bool:
    """Check if a field type is nullable (ends with ?)."""
    if isinstance(field_type, str):
        return field_type.endswith("?")
    # Complex types (enum, list) are not nullable
    return False


def base_type(field_type: str | dict) -> str:
    """Get the base type name without nullable suffix."""
    if isinstance(field_type, str):
        return field_type.rstrip("?")
    if isinstance(field_type, dict):
        if "enum" in field_type:
            return "enum"
        if "list" in field_type:
            return "list"
    return "unknown"


def is_valid_field_type(field_type: str | dict) -> bool:
    """Check if a field type definition is valid."""
    if isinstance(field_type, str):
        return field_type in SIMPLE_FIELD_TYPES
    if isinstance(field_type, dict):
        if "enum" in field_type:
            vals = field_type["enum"]
            return isinstance(vals, list) and len(vals) > 0 and all(isinstance(v, str) for v in vals)
        if "list" in field_type:
            inner = field_type["list"]
            return isinstance(inner, str) and inner in {"string", "int", "float"}
    return False


def now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
