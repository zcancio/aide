"""
AIde Kernel — Reducer (v3 Unified Entity Model)

Pure function: (snapshot, event) → ReduceResult
No side effects. No IO. No AI calls. Deterministic.

Given the same sequence of events, produces the same snapshot every time.

v3 key changes:
- schema.create/update/remove replace collection.create/update/remove
- entity.create/update/remove use path-based addressing
- entities are top-level (not nested in collections)
- TypeScript interfaces define field schemas
- _pos for fractional ordering, _shape for grid layout
"""

from __future__ import annotations

import copy
from typing import Any

from engine.kernel.ts_parser import parse_interface_cached, validate_entity_fields
from engine.kernel.types import (
    Event,
    ReduceResult,
    Warning,
    is_valid_id,
    parse_entity_path,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def empty_state() -> dict[str, Any]:
    """
    The initial snapshot when an aide has zero events.
    Only block_root exists.
    """
    return {
        "version": 3,
        "meta": {},
        "schemas": {},
        "entities": {},
        "blocks": {
            "block_root": {"type": "root", "children": []},
        },
        "styles": {},
        "annotations": [],
    }


def reduce(snapshot: dict[str, Any], event: Event) -> ReduceResult:
    """
    Apply one event to the current snapshot.
    Returns new snapshot + applied flag + warnings/errors.

    Pure function. The returned snapshot is a new dict (deep copy on mutation paths).
    The input snapshot is never modified.
    """
    handler = _HANDLERS.get(event.type)
    if handler is None:
        return ReduceResult(
            snapshot=snapshot,
            applied=False,
            error=f"UNKNOWN_PRIMITIVE: {event.type}",
        )

    # Deep copy so we never mutate the input
    snap = copy.deepcopy(snapshot)
    return handler(snap, event)


def replay(events: list[Event]) -> dict[str, Any]:
    """
    Rebuild snapshot from scratch by reducing over all events.
    replay(events) == reduce(reduce(reduce(empty(), e1), e2), e3)...
    """
    snapshot = empty_state()
    for event in events:
        result = reduce(snapshot, event)
        if result.applied:
            snapshot = result.snapshot
    return snapshot


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _reject(snap: dict, code: str, msg: str) -> ReduceResult:
    return ReduceResult(snapshot=snap, applied=False, error=f"{code}: {msg}")


def _ok(snap: dict, warnings: list[Warning] | None = None) -> ReduceResult:
    return ReduceResult(snapshot=snap, applied=True, warnings=warnings or [])


def _get_entity_at_path(snap: dict, path: str) -> tuple[dict | None, str | None]:
    """
    Resolve an entity path to (entity_dict, error_message).

    Path formats:
      "grocery_list"                    → top-level entity
      "grocery_list/items/item_milk"   → child entity

    For child paths: entity_id/field_name/child_id
    Returns (entity, None) on success or (None, error_message) on failure.
    """
    segments = parse_entity_path(path)
    if not segments:
        return None, f"Invalid path: {path!r}"

    if len(segments) == 1:
        entity = snap["entities"].get(segments[0])
        if entity is None or entity.get("_removed"):
            return None, f"Entity not found: {segments[0]!r}"
        return entity, None

    # Navigate nested path: entity_id / field_name / child_id / field_name / ...
    # Pattern: segments alternate between entity and field
    # e.g. ["grocery_list", "items", "item_milk"]
    # → snap.entities["grocery_list"]["items"]["item_milk"]
    top_id = segments[0]
    current = snap["entities"].get(top_id)
    if current is None or current.get("_removed"):
        return None, f"Entity not found: {top_id!r}"

    for i in range(1, len(segments), 2):
        field_name = segments[i]
        if field_name not in current:
            return None, f"Field {field_name!r} not found on entity at path segment {i}"
        child_collection = current[field_name]
        if not isinstance(child_collection, dict):
            return None, f"Field {field_name!r} is not a collection"

        if i + 1 < len(segments):
            child_id = segments[i + 1]
            child = child_collection.get(child_id)
            if child is None or child.get("_removed"):
                return None, f"Child {child_id!r} not found in field {field_name!r}"
            current = child
        else:
            return None, f"Path {path!r} ends on a field (expected entity_id after field)"

    return current, None


def _set_entity_at_path(snap: dict, path: str, entity: dict) -> str | None:
    """
    Set entity at path. Returns error message or None on success.
    Creates intermediate collections if needed.
    """
    segments = parse_entity_path(path)
    if not segments:
        return f"Invalid path: {path!r}"

    if len(segments) == 1:
        snap["entities"][segments[0]] = entity
        return None

    # Navigate to parent entity, creating path if needed
    top_id = segments[0]
    current = snap["entities"].get(top_id)
    if current is None or current.get("_removed"):
        return f"Parent entity not found: {top_id!r}"

    for i in range(1, len(segments) - 2, 2):
        field_name = segments[i]
        if field_name not in current:
            return f"Field {field_name!r} not found on entity"
        child_col = current[field_name]
        if not isinstance(child_col, dict):
            return f"Field {field_name!r} is not a collection"
        child_id = segments[i + 1]
        child = child_col.get(child_id)
        if child is None or child.get("_removed"):
            return f"Child entity {child_id!r} not found"
        current = child

    # Now at parent entity, set in field collection
    field_name = segments[-2]
    child_id = segments[-1]
    if field_name not in current:
        # Auto-create the field as a Record collection
        current[field_name] = {}
    field_col = current[field_name]
    if not isinstance(field_col, dict):
        return f"Field {field_name!r} is not a collection"
    field_col[child_id] = entity
    return None


def _remove_entity_at_path(snap: dict, path: str) -> str | None:
    """
    Soft-remove entity at path. Returns error message or None on success.
    """
    segments = parse_entity_path(path)
    if not segments:
        return f"Invalid path: {path!r}"

    entity, err = _get_entity_at_path(snap, path)
    if err:
        return err

    entity["_removed"] = True
    # Recursively mark all nested children as removed
    _remove_nested_children(entity)
    return None


def _remove_nested_children(entity: dict) -> None:
    """Recursively soft-remove all children in Record fields."""
    for key, value in entity.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            # Check if this looks like a child collection (values are entity dicts)
            for child_id, child in value.items():
                if isinstance(child, dict) and not child_id.startswith("_"):
                    child["_removed"] = True
                    _remove_nested_children(child)


def _validate_fields_against_schema(
    fields: dict[str, Any],
    schema_id: str,
    snap: dict,
) -> list[str]:
    """
    Validate entity fields against a schema's TypeScript interface.
    Returns list of error messages.
    """
    schema = snap["schemas"].get(schema_id)
    if schema is None:
        return [f"Schema {schema_id!r} not found"]

    interface_src = schema.get("interface", "")
    if not interface_src:
        return []  # No interface defined — accept anything

    iface = parse_interface_cached(interface_src)
    if iface is None:
        return [f"Failed to parse interface for schema {schema_id!r}"]

    return validate_entity_fields(fields, iface)


# ---------------------------------------------------------------------------
# Handler: schema.create
# ---------------------------------------------------------------------------


def _handle_schema_create(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    schema_id = p.get("id", "")

    if not schema_id:
        return _reject(snap, "MISSING_ID", "schema.create requires 'id'")
    if not is_valid_id(schema_id):
        return _reject(snap, "INVALID_ID", f"Schema ID {schema_id!r} is not a valid identifier")

    existing = snap["schemas"].get(schema_id)
    if existing and not existing.get("_removed"):
        return _reject(snap, "ALREADY_EXISTS", f"Schema {schema_id!r} already exists")

    interface_src = p.get("interface", "")
    if not interface_src:
        return _reject(snap, "MISSING_INTERFACE", "schema.create requires 'interface'")

    # Validate the interface can be parsed
    iface = parse_interface_cached(interface_src)
    if iface is None:
        return _reject(snap, "INVALID_INTERFACE", f"Failed to parse TypeScript interface for schema {schema_id!r}")

    schema_def: dict[str, Any] = {
        "interface": interface_src,
    }
    if "render_html" in p:
        schema_def["render_html"] = p["render_html"]
    if "render_text" in p:
        schema_def["render_text"] = p["render_text"]
    if "styles" in p:
        schema_def["styles"] = p["styles"]

    snap["schemas"][schema_id] = schema_def
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: schema.update
# ---------------------------------------------------------------------------


def _handle_schema_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    schema_id = p.get("id", "")

    if not schema_id:
        return _reject(snap, "MISSING_ID", "schema.update requires 'id'")

    schema = snap["schemas"].get(schema_id)
    if schema is None or schema.get("_removed"):
        return _reject(snap, "NOT_FOUND", f"Schema {schema_id!r} not found")

    warnings: list[Warning] = []

    if "interface" in p:
        interface_src = p["interface"]
        iface = parse_interface_cached(interface_src)
        if iface is None:
            return _reject(snap, "INVALID_INTERFACE", f"Failed to parse TypeScript interface for schema {schema_id!r}")
        schema["interface"] = interface_src

        # Warn if field changes might affect existing entities
        old_iface = parse_interface_cached(snap["schemas"][schema_id].get("interface", ""))
        if old_iface and iface:
            removed_fields = set(old_iface.fields.keys()) - set(iface.fields.keys())
            if removed_fields:
                warnings.append(
                    Warning(
                        code="FIELDS_REMOVED",
                        message=(
                            f"Interface update removed fields: {sorted(removed_fields)}. Existing entity data retained."
                        ),
                    )
                )

    if "render_html" in p:
        schema["render_html"] = p["render_html"]
    if "render_text" in p:
        schema["render_text"] = p["render_text"]
    if "styles" in p:
        schema["styles"] = p["styles"]

    return _ok(snap, warnings)


# ---------------------------------------------------------------------------
# Handler: schema.remove
# ---------------------------------------------------------------------------


def _handle_schema_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    schema_id = p.get("id", "")

    if not schema_id:
        return _reject(snap, "MISSING_ID", "schema.remove requires 'id'")

    schema = snap["schemas"].get(schema_id)
    if schema is None or schema.get("_removed"):
        return _reject(snap, "NOT_FOUND", f"Schema {schema_id!r} not found")

    # Check if any entities reference this schema
    for entity_id, entity in snap["entities"].items():
        if entity.get("_removed"):
            continue
        if entity.get("_schema") == schema_id:
            return _reject(
                snap,
                "SCHEMA_IN_USE",
                f"Schema {schema_id!r} is used by entity {entity_id!r}. Remove entities first.",
            )

    schema["_removed"] = True
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: entity.create
# ---------------------------------------------------------------------------


def _handle_entity_create(snap: dict, event: Event) -> ReduceResult:
    p = event.payload

    # 'id' can be a simple ID or a path (for creating a nested child)
    entity_path = p.get("id", "")
    if not entity_path:
        return _reject(snap, "MISSING_ID", "entity.create requires 'id'")

    segments = parse_entity_path(entity_path)
    if not segments:
        return _reject(snap, "INVALID_PATH", f"Invalid entity path: {entity_path!r}")

    # Check entity doesn't already exist
    existing, _ = _get_entity_at_path(snap, entity_path)
    if existing is not None:
        return _reject(snap, "ALREADY_EXISTS", f"Entity at path {entity_path!r} already exists")

    # Build entity from payload (exclude system fields)
    entity: dict[str, Any] = {}
    SYSTEM_KEYS = {"id", "_schema", "_pos", "_view", "_shape", "_removed", "_created_seq", "_updated_seq"}

    schema_id = p.get("_schema")
    if schema_id:
        if snap["schemas"].get(schema_id) is None:
            return _reject(snap, "SCHEMA_NOT_FOUND", f"Schema {schema_id!r} not found")
        entity["_schema"] = schema_id

    if "_pos" in p:
        entity["_pos"] = p["_pos"]

    if "_view" in p:
        entity["_view"] = p["_view"]

    # Copy user-defined fields
    for key, value in p.items():
        if key not in SYSTEM_KEYS:
            entity[key] = value

    # Validate fields against schema
    if schema_id:
        field_data = {k: v for k, v in entity.items() if not k.startswith("_")}
        errors = _validate_fields_against_schema(field_data, schema_id, snap)
        if errors:
            return _reject(snap, "VALIDATION_ERROR", "; ".join(errors))

    err = _set_entity_at_path(snap, entity_path, entity)
    if err:
        return _reject(snap, "PATH_ERROR", err)

    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: entity.update
# ---------------------------------------------------------------------------


def _handle_entity_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload

    entity_path = p.get("id", "")
    if not entity_path:
        return _reject(snap, "MISSING_ID", "entity.update requires 'id'")

    entity, err = _get_entity_at_path(snap, entity_path)
    if err:
        return _reject(snap, "NOT_FOUND", err)

    SYSTEM_KEYS = {"id", "_schema", "_removed", "_created_seq", "_updated_seq"}
    warnings: list[Warning] = []

    # Apply updates
    for key, value in p.items():
        if key in SYSTEM_KEYS or key == "id":
            continue

        if key == "_pos":
            entity["_pos"] = value
            continue

        if key == "_view":
            entity["_view"] = value
            continue

        if value is None:
            # null means remove the child or field
            if key in entity and isinstance(entity[key], dict) and not key.startswith("_"):
                # Could be a child collection field or entity removal
                # For now, remove the key entirely
                del entity[key]
            elif key in entity:
                del entity[key]
            continue

        # Check if this key is a Record field (child collection) — merge, not replace
        existing_val = entity.get(key)
        if isinstance(value, dict) and isinstance(existing_val, dict) and not key.startswith("_"):
            # Merge child collection updates
            for child_id, child_data in value.items():
                if child_data is None:
                    # Remove child
                    if child_id in existing_val:
                        existing_val[child_id]["_removed"] = True
                        _remove_nested_children(existing_val[child_id])
                elif child_id in existing_val and not existing_val[child_id].get("_removed"):
                    # Update existing child — merge fields
                    for ck, cv in child_data.items():
                        if ck not in {"_removed", "_created_seq", "_updated_seq"}:
                            existing_val[child_id][ck] = cv
                else:
                    # Create new child
                    existing_val[child_id] = child_data
        else:
            entity[key] = value

    # Validate updated fields against schema
    schema_id = entity.get("_schema")
    if schema_id:
        field_data = {k: v for k, v in entity.items() if not k.startswith("_")}
        errors = _validate_fields_against_schema(field_data, schema_id, snap)
        if errors:
            # Warn rather than reject on updates (partial updates are valid)
            warnings.extend(Warning(code="VALIDATION_WARNING", message=e) for e in errors)

    return _ok(snap, warnings)


# ---------------------------------------------------------------------------
# Handler: entity.remove
# ---------------------------------------------------------------------------


def _handle_entity_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload

    entity_path = p.get("id", "")
    if not entity_path:
        return _reject(snap, "MISSING_ID", "entity.remove requires 'id'")

    err = _remove_entity_at_path(snap, entity_path)
    if err:
        return _reject(snap, "NOT_FOUND", err)

    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: block.set
# ---------------------------------------------------------------------------


def _handle_block_set(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    block_id = p.get("id", "")
    if not block_id:
        return _reject(snap, "MISSING_ID", "block.set requires 'id'")

    block_type = p.get("type", "")
    if not block_type:
        return _reject(snap, "MISSING_TYPE", "block.set requires 'type'")

    parent_id = p.get("parent", "block_root")

    # Validate parent exists
    if parent_id not in snap["blocks"]:
        return _reject(snap, "PARENT_NOT_FOUND", f"Parent block {parent_id!r} not found")

    existing = snap["blocks"].get(block_id)
    old_parent_id = None
    if existing:
        # Find current parent to remove from its children
        for bid, blk in snap["blocks"].items():
            if bid != block_id and block_id in blk.get("children", []):
                old_parent_id = bid
                break

    # Build block
    block: dict[str, Any] = {"type": block_type}
    for key, value in p.items():
        if key not in ("id", "type", "parent"):
            block[key] = value
    if "children" not in block:
        block["children"] = []

    snap["blocks"][block_id] = block

    # Handle reparenting
    if old_parent_id and old_parent_id != parent_id:
        old_parent = snap["blocks"][old_parent_id]
        old_parent["children"] = [c for c in old_parent.get("children", []) if c != block_id]

    # Add to parent if not already there
    parent = snap["blocks"][parent_id]
    if "children" not in parent:
        parent["children"] = []
    if block_id not in parent["children"]:
        parent["children"].append(block_id)

    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: block.remove
# ---------------------------------------------------------------------------


def _handle_block_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    block_id = p.get("id", "")
    if not block_id:
        return _reject(snap, "MISSING_ID", "block.remove requires 'id'")

    if block_id == "block_root":
        return _reject(snap, "CANNOT_REMOVE_ROOT", "Cannot remove block_root")

    if block_id not in snap["blocks"]:
        return _reject(snap, "NOT_FOUND", f"Block {block_id!r} not found")

    # Remove from parent's children list
    for _bid, blk in snap["blocks"].items():
        if block_id in blk.get("children", []):
            blk["children"] = [c for c in blk["children"] if c != block_id]

    # Recursively remove descendants
    def _remove_subtree(bid: str) -> None:
        blk = snap["blocks"].get(bid)
        if blk is None:
            return
        for child_id in blk.get("children", []):
            _remove_subtree(child_id)
        del snap["blocks"][bid]

    _remove_subtree(block_id)
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: block.reorder
# ---------------------------------------------------------------------------


def _handle_block_reorder(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    parent_id = p.get("parent", "block_root")
    order = p.get("order", [])

    parent = snap["blocks"].get(parent_id)
    if parent is None:
        return _reject(snap, "NOT_FOUND", f"Block {parent_id!r} not found")

    # Validate all IDs in order are children
    current_children = set(parent.get("children", []))
    new_set = set(order)
    if current_children != new_set:
        return _reject(snap, "ORDER_MISMATCH", "order must contain exactly the current children")

    parent["children"] = order
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: style.set
# ---------------------------------------------------------------------------


def _handle_style_set(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    for key, value in p.items():
        snap["styles"][key] = value
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: meta.update
# ---------------------------------------------------------------------------


def _handle_meta_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    for key, value in p.items():
        snap["meta"][key] = value
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler: meta.annotate
# ---------------------------------------------------------------------------


def _handle_meta_annotate(snap: dict, event: Event) -> ReduceResult:
    from engine.kernel.types import now_iso

    p = event.payload
    note = p.get("note", "")
    if not note:
        return _reject(snap, "MISSING_NOTE", "meta.annotate requires 'note'")

    annotation = {
        "note": note,
        "timestamp": p.get("timestamp", now_iso()),
        "pinned": p.get("pinned", False),
    }
    if "author" in p:
        annotation["author"] = p["author"]

    snap["annotations"].append(annotation)
    return _ok(snap)


# ---------------------------------------------------------------------------
# Handler dispatch table
# ---------------------------------------------------------------------------

_HANDLERS = {
    "schema.create": _handle_schema_create,
    "schema.update": _handle_schema_update,
    "schema.remove": _handle_schema_remove,
    "entity.create": _handle_entity_create,
    "entity.update": _handle_entity_update,
    "entity.remove": _handle_entity_remove,
    "block.set": _handle_block_set,
    "block.remove": _handle_block_remove,
    "block.reorder": _handle_block_reorder,
    "style.set": _handle_style_set,
    "meta.update": _handle_meta_update,
    "meta.annotate": _handle_meta_annotate,
}
