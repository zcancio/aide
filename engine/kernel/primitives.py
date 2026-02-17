"""
AIde Kernel — Primitive Validation

Validates primitive payloads before they reach the reducer.
Every state change goes through one of 22 primitive types.
Validation is structural (well-formed?) not semantic (will it apply?).
The reducer handles semantic checks (does the collection exist? etc.).

Reference: aide_primitive_schemas.md
"""

from __future__ import annotations

from typing import Any

from engine.kernel.types import (
    BLOCK_TYPES,
    CONSTRAINT_RULES,
    PRIMITIVE_TYPES,
    VIEW_TYPES,
    is_valid_field_type,
    is_valid_id,
    is_valid_ref,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_primitive(type: str, payload: dict[str, Any]) -> list[str]:
    """
    Validate a primitive's type and payload structure.
    Returns a list of error strings. Empty list = valid.

    This checks structural validity only:
    - Is the type recognized?
    - Is the payload a dict?
    - Are required fields present?
    - Are IDs well-formed?
    - Are refs well-formed?

    It does NOT check whether referenced entities/collections exist.
    That's the reducer's job.
    """
    errors: list[str] = []

    # Universal: type must be known
    if type not in PRIMITIVE_TYPES:
        errors.append(f"Unknown primitive type: {type}")
        return errors  # can't validate payload for unknown type

    # Universal: payload must be a dict
    if not isinstance(payload, dict):
        errors.append("Payload must be a non-null object")
        return errors

    # Dispatch to type-specific validator
    validator = _VALIDATORS.get(type)
    if validator:
        errors.extend(validator(payload))

    return errors


# ---------------------------------------------------------------------------
# Per-primitive validators
# ---------------------------------------------------------------------------


def _validate_entity_create(p: dict) -> list[str]:
    errors: list[str] = []
    if "collection" not in p:
        errors.append("entity.create requires 'collection'")
    elif not is_valid_id(p["collection"]):
        errors.append(f"Invalid collection ID: {p['collection']}")

    if "id" in p and p["id"] is not None and not is_valid_id(p["id"]):
        errors.append(f"Invalid entity ID: {p['id']}")

    if "fields" not in p:
        errors.append("entity.create requires 'fields'")
    elif not isinstance(p["fields"], dict):
        errors.append("'fields' must be an object")

    return errors


def _validate_entity_update(p: dict) -> list[str]:
    errors: list[str] = []
    has_ref = "ref" in p
    has_filter = "filter" in p
    has_cell_ref = "cell_ref" in p  # Grid cell reference (resolved by backend)

    if not has_ref and not has_filter and not has_cell_ref:
        errors.append("entity.update requires 'ref', 'filter', or 'cell_ref'")
    elif sum([has_ref, has_filter, has_cell_ref]) > 1:
        errors.append("entity.update: provide only one of 'ref', 'filter', or 'cell_ref'")

    if has_ref and not is_valid_ref(p["ref"]):
        errors.append(f"Invalid ref: {p['ref']}")

    if has_filter:
        f = p["filter"]
        if not isinstance(f, dict):
            errors.append("'filter' must be an object")
        elif "collection" not in f:
            errors.append("filter requires 'collection'")

    if has_cell_ref:
        if not isinstance(p["cell_ref"], str):
            errors.append("'cell_ref' must be a string")
        if "collection" not in p:
            errors.append("cell_ref requires 'collection'")

    if "fields" not in p:
        errors.append("entity.update requires 'fields'")
    elif not isinstance(p["fields"], dict):
        errors.append("'fields' must be an object")

    return errors


def _validate_entity_remove(p: dict) -> list[str]:
    errors: list[str] = []
    if "ref" not in p:
        errors.append("entity.remove requires 'ref'")
    elif not is_valid_ref(p["ref"]):
        errors.append(f"Invalid ref: {p['ref']}")
    return errors


def _validate_collection_create(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("collection.create requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid collection ID: {p['id']}")

    if "schema" not in p:
        errors.append("collection.create requires 'schema'")
    elif not isinstance(p["schema"], dict):
        errors.append("'schema' must be an object")
    else:
        for field_name, field_type in p["schema"].items():
            if not is_valid_id(field_name):
                errors.append(f"Invalid field name in schema: {field_name}")
            if not is_valid_field_type(field_type):
                errors.append(f"Invalid field type for '{field_name}': {field_type}")

    return errors


def _validate_collection_update(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("collection.update requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid collection ID: {p['id']}")
    return errors


def _validate_collection_remove(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("collection.remove requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid collection ID: {p['id']}")
    return errors


def _validate_grid_create(p: dict) -> list[str]:
    """Validate grid.create primitive for batch entity creation."""
    errors: list[str] = []
    if "collection" not in p:
        errors.append("grid.create requires 'collection'")
    elif not is_valid_id(p["collection"]):
        errors.append(f"Invalid collection ID: {p['collection']}")

    if "rows" not in p:
        errors.append("grid.create requires 'rows'")
    elif not isinstance(p["rows"], int) or p["rows"] < 1:
        errors.append("'rows' must be a positive integer")

    if "cols" not in p:
        errors.append("grid.create requires 'cols'")
    elif not isinstance(p["cols"], int) or p["cols"] < 1:
        errors.append("'cols' must be a positive integer")

    return errors


def _validate_grid_query(p: dict) -> list[str]:
    """Validate grid.query primitive for cell lookups."""
    errors: list[str] = []
    if "cell_ref" not in p:
        errors.append("grid.query requires 'cell_ref'")
    elif not isinstance(p["cell_ref"], str):
        errors.append("'cell_ref' must be a string")

    if "collection" not in p:
        errors.append("grid.query requires 'collection'")
    elif not is_valid_id(p["collection"]):
        errors.append(f"Invalid collection ID: {p['collection']}")

    return errors


def _validate_field_add(p: dict) -> list[str]:
    errors: list[str] = []
    if "collection" not in p:
        errors.append("field.add requires 'collection'")
    elif not is_valid_id(p["collection"]):
        errors.append(f"Invalid collection ID: {p['collection']}")

    if "name" not in p:
        errors.append("field.add requires 'name'")
    elif not is_valid_id(p["name"]):
        errors.append(f"Invalid field name: {p['name']}")

    if "type" not in p:
        errors.append("field.add requires 'type'")
    elif not is_valid_field_type(p["type"]):
        errors.append(f"Invalid field type: {p['type']}")

    return errors


def _validate_field_update(p: dict) -> list[str]:
    errors: list[str] = []
    if "collection" not in p:
        errors.append("field.update requires 'collection'")
    elif not is_valid_id(p["collection"]):
        errors.append(f"Invalid collection ID: {p['collection']}")

    if "name" not in p:
        errors.append("field.update requires 'name'")
    elif not is_valid_id(p["name"]):
        errors.append(f"Invalid field name: {p['name']}")

    return errors


def _validate_field_remove(p: dict) -> list[str]:
    errors: list[str] = []
    if "collection" not in p:
        errors.append("field.remove requires 'collection'")
    elif not is_valid_id(p["collection"]):
        errors.append(f"Invalid collection ID: {p['collection']}")

    if "name" not in p:
        errors.append("field.remove requires 'name'")
    elif not is_valid_id(p["name"]):
        errors.append(f"Invalid field name: {p['name']}")

    return errors


def _validate_relationship_set(p: dict) -> list[str]:
    errors: list[str] = []
    for key in ("from", "to", "type"):
        if key not in p:
            errors.append(f"relationship.set requires '{key}'")

    if "from" in p and not is_valid_ref(p["from"]):
        errors.append(f"Invalid 'from' ref: {p['from']}")
    if "to" in p and not is_valid_ref(p["to"]):
        errors.append(f"Invalid 'to' ref: {p['to']}")
    if "type" in p and not is_valid_id(p["type"]):
        errors.append(f"Invalid relationship type: {p['type']}")

    return errors


def _validate_relationship_constrain(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("relationship.constrain requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid constraint ID: {p['id']}")

    if "rule" not in p:
        errors.append("relationship.constrain requires 'rule'")
    elif p["rule"] not in CONSTRAINT_RULES:
        errors.append(f"Unknown constraint rule: {p['rule']}")

    return errors


def _validate_block_set(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("block.set requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid block ID: {p['id']}")

    # type is required for creation, optional for update — reducer decides
    if "type" in p and p["type"] not in BLOCK_TYPES:
        errors.append(f"Unknown block type: {p['type']}")

    if "parent" in p and not is_valid_id(p["parent"]):
        errors.append(f"Invalid parent block ID: {p['parent']}")

    return errors


def _validate_block_remove(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("block.remove requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid block ID: {p['id']}")
    return errors


def _validate_block_reorder(p: dict) -> list[str]:
    errors: list[str] = []
    if "parent" not in p:
        errors.append("block.reorder requires 'parent'")
    elif not is_valid_id(p["parent"]):
        errors.append(f"Invalid parent block ID: {p['parent']}")

    if "children" not in p:
        errors.append("block.reorder requires 'children'")
    elif not isinstance(p["children"], list):
        errors.append("'children' must be a list")
    else:
        for child_id in p["children"]:
            if not isinstance(child_id, str) or not is_valid_id(child_id):
                errors.append(f"Invalid child block ID: {child_id}")
    return errors


def _validate_view_create(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("view.create requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid view ID: {p['id']}")

    if "type" not in p:
        errors.append("view.create requires 'type'")
    elif p["type"] not in VIEW_TYPES:
        errors.append(f"Unknown view type: {p['type']}. Known: {VIEW_TYPES}")

    if "source" not in p:
        errors.append("view.create requires 'source'")
    elif not is_valid_id(p["source"]):
        errors.append(f"Invalid source collection ID: {p['source']}")

    return errors


def _validate_view_update(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("view.update requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid view ID: {p['id']}")

    if "type" in p and p["type"] not in VIEW_TYPES:
        errors.append(f"Unknown view type: {p['type']}")

    return errors


def _validate_view_remove(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("view.remove requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid view ID: {p['id']}")
    return errors


def _validate_style_set(p: dict) -> list[str]:
    # All keys accepted — unknown tokens stored for forward compatibility
    return []


def _validate_style_set_entity(p: dict) -> list[str]:
    errors: list[str] = []
    if "ref" not in p:
        errors.append("style.set_entity requires 'ref'")
    elif not is_valid_ref(p["ref"]):
        errors.append(f"Invalid ref: {p['ref']}")

    if "styles" not in p:
        errors.append("style.set_entity requires 'styles'")
    elif not isinstance(p["styles"], dict):
        errors.append("'styles' must be an object")

    return errors


def _validate_meta_update(p: dict) -> list[str]:
    # All keys accepted — unknown properties stored
    return []


def _validate_meta_annotate(p: dict) -> list[str]:
    errors: list[str] = []
    if "note" not in p:
        errors.append("meta.annotate requires 'note'")
    elif not isinstance(p["note"], str):
        errors.append("'note' must be a string")
    return errors


def _validate_meta_constrain(p: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in p:
        errors.append("meta.constrain requires 'id'")
    elif not is_valid_id(p["id"]):
        errors.append(f"Invalid constraint ID: {p['id']}")

    if "rule" not in p:
        errors.append("meta.constrain requires 'rule'")
    elif p["rule"] not in CONSTRAINT_RULES:
        errors.append(f"Unknown constraint rule: {p['rule']}")

    return errors


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_VALIDATORS: dict[str, Any] = {
    "entity.create": _validate_entity_create,
    "entity.update": _validate_entity_update,
    "entity.remove": _validate_entity_remove,
    "collection.create": _validate_collection_create,
    "collection.update": _validate_collection_update,
    "collection.remove": _validate_collection_remove,
    "grid.create": _validate_grid_create,
    "grid.query": _validate_grid_query,
    "field.add": _validate_field_add,
    "field.update": _validate_field_update,
    "field.remove": _validate_field_remove,
    "relationship.set": _validate_relationship_set,
    "relationship.constrain": _validate_relationship_constrain,
    "block.set": _validate_block_set,
    "block.remove": _validate_block_remove,
    "block.reorder": _validate_block_reorder,
    "view.create": _validate_view_create,
    "view.update": _validate_view_update,
    "view.remove": _validate_view_remove,
    "style.set": _validate_style_set,
    "style.set_entity": _validate_style_set_entity,
    "meta.update": _validate_meta_update,
    "meta.annotate": _validate_meta_annotate,
    "meta.constrain": _validate_meta_constrain,
}
