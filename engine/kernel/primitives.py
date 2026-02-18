"""
AIde Kernel — Primitive Validators (v3 Unified Entity Model)

Structural validation of primitive payloads before reduction.
Returns a list of error strings — empty means valid.

v3 primitives:
  schema.create, schema.update, schema.remove
  entity.create, entity.update, entity.remove
  block.set, block.remove, block.reorder
  style.set
  meta.update, meta.annotate
"""

from __future__ import annotations

from typing import Any

from engine.kernel.ts_parser import parse_interface
from engine.kernel.types import PRIMITIVE_TYPES, is_valid_id, parse_entity_path

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_primitive(primitive_type: str, payload: dict[str, Any]) -> list[str]:
    """
    Validate the structural correctness of a primitive payload.

    Returns an empty list if valid, or a list of error messages if invalid.
    Only structural checks — semantic checks (entity existence, schema consistency)
    happen in the reducer.
    """
    if primitive_type not in PRIMITIVE_TYPES:
        return [f"Unknown primitive type: {primitive_type!r}"]

    validator = _VALIDATORS.get(primitive_type)
    if validator is None:
        return []  # No validator defined — pass through

    return validator(payload)


# ---------------------------------------------------------------------------
# schema.* validators
# ---------------------------------------------------------------------------


def _validate_schema_create(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    schema_id = p.get("id")
    if not schema_id:
        errors.append("Missing required field: 'id'")
    elif not isinstance(schema_id, str) or not is_valid_id(schema_id):
        errors.append(f"'id' must be a valid snake_case identifier, got {schema_id!r}")

    interface_src = p.get("interface")
    if not interface_src:
        errors.append("Missing required field: 'interface'")
    elif not isinstance(interface_src, str):
        errors.append("'interface' must be a string (TypeScript interface source)")
    else:
        iface = parse_interface(interface_src)
        if iface is None:
            errors.append(f"'interface' could not be parsed as a TypeScript interface: {interface_src!r}")

    if "render_html" in p and not isinstance(p["render_html"], str):
        errors.append("'render_html' must be a string (Mustache template)")

    if "render_text" in p and not isinstance(p["render_text"], str):
        errors.append("'render_text' must be a string (Mustache template)")

    if "styles" in p and not isinstance(p["styles"], str):
        errors.append("'styles' must be a string (CSS)")

    return errors


def _validate_schema_update(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    schema_id = p.get("id")
    if not schema_id:
        errors.append("Missing required field: 'id'")
    elif not isinstance(schema_id, str):
        errors.append("'id' must be a string")

    if "interface" in p:
        interface_src = p["interface"]
        if not isinstance(interface_src, str):
            errors.append("'interface' must be a string (TypeScript interface source)")
        else:
            iface = parse_interface(interface_src)
            if iface is None:
                errors.append("'interface' could not be parsed as a TypeScript interface")

    if "render_html" in p and not isinstance(p["render_html"], str):
        errors.append("'render_html' must be a string")
    if "render_text" in p and not isinstance(p["render_text"], str):
        errors.append("'render_text' must be a string")
    if "styles" in p and not isinstance(p["styles"], str):
        errors.append("'styles' must be a string")

    return errors


def _validate_schema_remove(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_id = p.get("id")
    if not schema_id:
        errors.append("Missing required field: 'id'")
    elif not isinstance(schema_id, str):
        errors.append("'id' must be a string")
    return errors


# ---------------------------------------------------------------------------
# entity.* validators
# ---------------------------------------------------------------------------


def _validate_entity_create(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    entity_path = p.get("id")
    if not entity_path:
        errors.append("Missing required field: 'id'")
    elif not isinstance(entity_path, str):
        errors.append("'id' must be a string (entity path)")
    else:
        segments = parse_entity_path(entity_path)
        if not segments:
            errors.append(f"'id' is not a valid entity path: {entity_path!r}")

    if "_schema" in p and not isinstance(p["_schema"], str):
        errors.append("'_schema' must be a string (schema ID)")

    if "_pos" in p and not isinstance(p["_pos"], int | float):
        errors.append("'_pos' must be a number (fractional index)")

    return errors


def _validate_entity_update(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    entity_path = p.get("id")
    if not entity_path:
        errors.append("Missing required field: 'id'")
    elif not isinstance(entity_path, str):
        errors.append("'id' must be a string (entity path)")
    else:
        segments = parse_entity_path(entity_path)
        if not segments:
            errors.append(f"'id' is not a valid entity path: {entity_path!r}")

    if "_pos" in p and not isinstance(p["_pos"], int | float):
        errors.append("'_pos' must be a number")

    return errors


def _validate_entity_remove(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    entity_path = p.get("id")
    if not entity_path:
        errors.append("Missing required field: 'id'")
    elif not isinstance(entity_path, str):
        errors.append("'id' must be a string (entity path)")
    else:
        segments = parse_entity_path(entity_path)
        if not segments:
            errors.append(f"'id' is not a valid entity path: {entity_path!r}")

    return errors


# ---------------------------------------------------------------------------
# block.* validators
# ---------------------------------------------------------------------------

_VALID_BLOCK_TYPES = {
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


def _validate_block_set(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    block_id = p.get("id")
    if not block_id:
        errors.append("Missing required field: 'id'")
    elif not isinstance(block_id, str) or not is_valid_id(block_id):
        errors.append(f"'id' must be a valid identifier, got {block_id!r}")

    block_type = p.get("type")
    if not block_type:
        errors.append("Missing required field: 'type'")
    elif block_type not in _VALID_BLOCK_TYPES:
        errors.append(f"'type' must be one of {sorted(_VALID_BLOCK_TYPES)}, got {block_type!r}")

    if "parent" in p and not isinstance(p["parent"], str):
        errors.append("'parent' must be a string (block ID)")

    return errors


def _validate_block_remove(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    block_id = p.get("id")
    if not block_id:
        errors.append("Missing required field: 'id'")
    elif not isinstance(block_id, str):
        errors.append("'id' must be a string")
    return errors


def _validate_block_reorder(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    order = p.get("order")
    if order is None:
        errors.append("Missing required field: 'order'")
    elif not isinstance(order, list):
        errors.append("'order' must be a list of block IDs")
    elif not all(isinstance(x, str) for x in order):
        errors.append("'order' must contain string block IDs")

    return errors


# ---------------------------------------------------------------------------
# style.* validators
# ---------------------------------------------------------------------------


def _validate_style_set(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not p:
        errors.append("style.set requires at least one style token")
    if not isinstance(p, dict):
        errors.append("style.set payload must be a dict of style tokens")
    return errors


# ---------------------------------------------------------------------------
# meta.* validators
# ---------------------------------------------------------------------------


def _validate_meta_update(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not p:
        errors.append("meta.update requires at least one field")
    return errors


def _validate_meta_annotate(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not p.get("note"):
        errors.append("meta.annotate requires 'note'")
    elif not isinstance(p["note"], str):
        errors.append("'note' must be a string")
    return errors


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_VALIDATORS: dict[str, Any] = {
    "schema.create": _validate_schema_create,
    "schema.update": _validate_schema_update,
    "schema.remove": _validate_schema_remove,
    "entity.create": _validate_entity_create,
    "entity.update": _validate_entity_update,
    "entity.remove": _validate_entity_remove,
    "block.set": _validate_block_set,
    "block.remove": _validate_block_remove,
    "block.reorder": _validate_block_reorder,
    "style.set": _validate_style_set,
    "meta.update": _validate_meta_update,
    "meta.annotate": _validate_meta_annotate,
}
