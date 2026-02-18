"""
AIde Kernel — TypeScript Interface Parser

Uses tree-sitter to parse TypeScript interfaces into structured field definitions.
Cache parsed results per schema — parse once, validate many times.

Reference: docs/eng_design/unified_entity_model.md
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

try:
    import tree_sitter_typescript as _ts_mod
    from tree_sitter import Language, Parser

    _LANG = Language(_ts_mod.language_typescript())
    _PARSER = Parser(_LANG)
    _TREE_SITTER_AVAILABLE = True
except Exception:
    _TREE_SITTER_AVAILABLE = False
    _LANG = None
    _PARSER = None


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ParsedField:
    """A parsed field from a TypeScript interface."""

    __slots__ = ("name", "optional", "ts_type", "kind", "record_item_type", "array_item_type", "union_values")

    def __init__(
        self,
        name: str,
        optional: bool,
        ts_type: str,
        kind: str,
        record_item_type: str | None = None,
        array_item_type: str | None = None,
        union_values: list[str] | None = None,
    ) -> None:
        self.name = name
        self.optional = optional
        self.ts_type = ts_type  # raw TypeScript type string
        self.kind = kind  # "scalar", "record", "array", "union", "unknown"
        self.record_item_type = record_item_type  # for Record<string, T> → T
        self.array_item_type = array_item_type  # for T[] → T
        self.union_values = union_values  # for "a" | "b" | "c" → ["a", "b", "c"]

    def __repr__(self) -> str:
        return f"ParsedField({self.name!r}, optional={self.optional}, kind={self.kind!r}, ts_type={self.ts_type!r})"


class ParsedInterface:
    """Result of parsing a TypeScript interface declaration."""

    __slots__ = ("name", "fields")

    def __init__(self, name: str, fields: dict[str, ParsedField]) -> None:
        self.name = name
        self.fields = fields  # field_name → ParsedField

    def __repr__(self) -> str:
        return f"ParsedInterface({self.name!r}, fields={list(self.fields.keys())})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_interface(code: str) -> ParsedInterface | None:
    """
    Parse a TypeScript interface declaration string.

    Returns ParsedInterface or None if parsing fails / no interface found.
    Uses tree-sitter when available, falls back to regex parsing.

    Results are NOT cached here — cache at the call site if needed.
    """
    if _TREE_SITTER_AVAILABLE:
        return _parse_with_tree_sitter(code)
    return _parse_with_regex(code)


@lru_cache(maxsize=256)
def parse_interface_cached(code: str) -> ParsedInterface | None:
    """
    Cached version of parse_interface. Safe to use for repeated validation.
    Cache is keyed by the exact interface string.
    """
    return parse_interface(code)


def validate_entity_fields(entity: dict[str, Any], interface: ParsedInterface) -> list[str]:
    """
    Validate entity fields against a parsed interface.
    Returns list of error messages (empty = valid).

    Only validates user-visible fields — ignores _schema, _pos, _view, _removed, etc.
    """
    errors: list[str] = []
    SYSTEM_KEYS = {"_schema", "_pos", "_view", "_removed", "_created_seq", "_updated_seq", "_shape"}

    for field_name, field_def in interface.fields.items():
        if field_name not in entity:
            if not field_def.optional:
                errors.append(f"Missing required field: {field_name!r}")
            continue

        value = entity[field_name]
        field_errors = _validate_value(value, field_def, field_name)
        errors.extend(field_errors)

    # Check for unknown fields (not in interface, not system keys)
    for key in entity:
        if key not in interface.fields and key not in SYSTEM_KEYS:
            errors.append(f"Unknown field: {key!r} (not in interface {interface.name!r})")

    return errors


def is_record_field(field: ParsedField) -> bool:
    """Return True if the field is a Record<string, T> (child collection)."""
    return field.kind == "record"


# ---------------------------------------------------------------------------
# Tree-sitter parsing (primary)
# ---------------------------------------------------------------------------


def _parse_with_tree_sitter(code: str) -> ParsedInterface | None:
    """Parse using tree-sitter. Primary implementation."""
    tree = _PARSER.parse(code.encode())
    root = tree.root_node

    for node in root.children:
        if node.type == "interface_declaration":
            return _extract_interface(node, code)

    return None


def _extract_interface(node: Any, code: str) -> ParsedInterface:
    """Extract interface name and fields from an interface_declaration node."""
    name = ""
    fields: dict[str, ParsedField] = {}

    for child in node.children:
        if child.type == "type_identifier":
            name = child.text.decode()
        elif child.type == "interface_body":
            for prop in child.children:
                if prop.type == "property_signature":
                    field = _extract_property(prop, code)
                    if field:
                        fields[field.name] = field

    return ParsedInterface(name=name, fields=fields)


def _extract_property(node: Any, code: str) -> ParsedField | None:
    """Extract a ParsedField from a property_signature node."""
    name = None
    optional = False
    type_node = None

    for child in node.children:
        if child.type == "property_identifier":
            name = child.text.decode()
        elif child.type == "?":
            optional = True
        elif child.type == "type_annotation":
            # Children: ":", <type_node>
            for tc in child.children:
                if tc.type not in (":", "type_annotation"):
                    type_node = tc

    if name is None or type_node is None:
        return None

    ts_type = type_node.text.decode()
    kind, record_item, array_item, union_vals = _classify_type_node(type_node)

    return ParsedField(
        name=name,
        optional=optional,
        ts_type=ts_type,
        kind=kind,
        record_item_type=record_item,
        array_item_type=array_item,
        union_values=union_vals,
    )


def _classify_type_node(node: Any) -> tuple[str, str | None, str | None, list[str] | None]:
    """
    Classify a type node into (kind, record_item_type, array_item_type, union_values).

    kind: "scalar" | "record" | "array" | "union" | "unknown"
    """
    t = node.type

    if t == "predefined_type":
        return "scalar", None, None, None

    if t == "type_identifier":
        return "scalar", None, None, None

    if t == "array_type":
        # T[]
        inner = node.children[0] if node.children else None
        item_type = inner.text.decode() if inner else "unknown"
        return "array", None, item_type, None

    if t == "generic_type":
        # Record<string, T> or other generics
        children = node.children
        if children and children[0].text.decode() == "Record":
            # Extract the second type argument (T in Record<string, T>)
            type_args = None
            for c in children:
                if c.type == "type_arguments":
                    type_args = c
                    break
            if type_args:
                args = [c for c in type_args.children if c.type not in ("<", ">", ",")]
                if len(args) >= 2:
                    item_type = args[1].text.decode()
                    return "record", item_type, None, None
        return "unknown", None, None, None

    if t == "union_type":
        # "a" | "b" | "c" → extract string literal values
        values = _extract_union_string_literals(node)
        if values:
            return "union", None, None, values
        # Non-string union (e.g., string | null) — treat as scalar
        return "scalar", None, None, None

    if t == "literal_type":
        return "scalar", None, None, None

    return "unknown", None, None, None


def _extract_union_string_literals(node: Any) -> list[str] | None:
    """Extract string literal values from a union_type node."""
    values = []
    for child in node.children:
        if child.type == "literal_type":
            for sub in child.children:
                if sub.type == "string":
                    # Extract string content (strip quotes)
                    text = sub.text.decode()
                    # Remove surrounding quotes
                    if text.startswith('"') and text.endswith('"'):
                        values.append(text[1:-1])
                    elif text.startswith("'") and text.endswith("'"):
                        values.append(text[1:-1])
    return values if values else None


# ---------------------------------------------------------------------------
# Regex fallback parsing (when tree-sitter unavailable)
# ---------------------------------------------------------------------------

_INTERFACE_RE = re.compile(
    r"interface\s+(\w+)\s*\{([^}]*)\}",
    re.DOTALL,
)
_FIELD_RE = re.compile(
    r"(\w+)(\?)?:\s*([^;]+);",
    re.DOTALL,
)
_RECORD_RE = re.compile(r"Record<string,\s*(\w+)>")
_ARRAY_RE = re.compile(r"(\w+)\[\]")
_UNION_RE = re.compile(r'"([^"]+)"')


def _parse_with_regex(code: str) -> ParsedInterface | None:
    """Fallback parser using regex. Less accurate but no native deps."""
    m = _INTERFACE_RE.search(code)
    if not m:
        return None

    name = m.group(1)
    body = m.group(2)
    fields: dict[str, ParsedField] = {}

    for fm in _FIELD_RE.finditer(body):
        field_name = fm.group(1)
        optional = fm.group(2) == "?"
        raw_type = fm.group(3).strip()

        kind, record_item, array_item, union_vals = _classify_raw_type(raw_type)
        fields[field_name] = ParsedField(
            name=field_name,
            optional=optional,
            ts_type=raw_type,
            kind=kind,
            record_item_type=record_item,
            array_item_type=array_item,
            union_values=union_vals,
        )

    return ParsedInterface(name=name, fields=fields)


def _classify_raw_type(raw: str) -> tuple[str, str | None, str | None, list[str] | None]:
    """Classify a raw type string into (kind, record_item, array_item, union_vals)."""
    raw = raw.strip()

    m = _RECORD_RE.match(raw)
    if m:
        return "record", m.group(1), None, None

    m = _ARRAY_RE.match(raw)
    if m:
        return "array", None, m.group(1), None

    if "|" in raw and '"' in raw:
        vals = _UNION_RE.findall(raw)
        if vals:
            return "union", None, None, vals

    # Scalar (string, number, boolean, Date, type_identifier, etc.)
    return "scalar", None, None, None


# ---------------------------------------------------------------------------
# Value validation
# ---------------------------------------------------------------------------

_SCALAR_TS_TYPES = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "Date": str,  # stored as ISO string
}


def _validate_value(value: Any, field: ParsedField, field_name: str) -> list[str]:
    """Validate a single value against a ParsedField definition."""
    errors: list[str] = []

    # None is allowed for optional fields
    if value is None:
        if not field.optional:
            errors.append(f"Field {field_name!r}: null not allowed (not optional)")
        return errors

    if field.kind == "scalar":
        errors.extend(_validate_scalar(value, field, field_name))
    elif field.kind == "record":
        if not isinstance(value, dict):
            errors.append(f"Field {field_name!r}: expected object (Record<string, {field.record_item_type}>)")
        # Children are validated separately via their own schema
    elif field.kind == "array":
        if not isinstance(value, list):
            errors.append(f"Field {field_name!r}: expected array ({field.array_item_type}[])")
        # Array item types validated loosely (strings/numbers acceptable)
    elif field.kind == "union":
        if field.union_values and value not in field.union_values:
            errors.append(f"Field {field_name!r}: {value!r} not in {field.union_values}")
    # "unknown" kind — accept anything

    return errors


def _validate_scalar(value: Any, field: ParsedField, field_name: str) -> list[str]:
    """Validate a scalar value (string, number, boolean, Date, type_identifier)."""
    ts_type = field.ts_type.strip()

    # Remove 'null |' or '| null' wrappers for nullable types
    cleaned = re.sub(r"\s*\|\s*null\s*", "", ts_type).strip()
    cleaned = re.sub(r"\s*\|\s*undefined\s*", "", cleaned).strip()

    if cleaned == "string":
        if not isinstance(value, str):
            return [f"Field {field_name!r}: expected string, got {type(value).__name__}"]
    elif cleaned == "number":
        if not isinstance(value, int | float) or isinstance(value, bool):
            return [f"Field {field_name!r}: expected number, got {type(value).__name__}"]
    elif cleaned == "boolean":
        if not isinstance(value, bool):
            return [f"Field {field_name!r}: expected boolean, got {type(value).__name__}"]
    elif cleaned == "Date":
        if not isinstance(value, str):
            return [f"Field {field_name!r}: expected ISO date string, got {type(value).__name__}"]
    # For type_identifier (custom type reference) — accept any dict or primitive
    # Deep validation happens when the child entity is processed with its schema

    return []
