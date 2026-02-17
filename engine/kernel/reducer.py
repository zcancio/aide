"""
AIde Kernel — Reducer

Pure function: (snapshot, event) → ReduceResult
No side effects. No IO. No AI calls. Deterministic.

Given the same sequence of events, produces the same snapshot every time.

Reference: aide_reducer_spec.md
"""

from __future__ import annotations

import copy
from typing import Any

from engine.kernel.types import (
    Event,
    ReduceResult,
    Warning,
    base_type,
    is_nullable_type,
    is_valid_field_type,
    parse_ref,
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
        "version": 1,
        "meta": {},
        "collections": {},
        "relationships": [],
        "relationship_types": {},
        "constraints": [],
        "blocks": {
            "block_root": {"type": "root", "children": []},
        },
        "views": {},
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


def _get_collection(snap: dict, coll_id: str) -> dict | None:
    """Lookup a non-removed collection."""
    coll = snap["collections"].get(coll_id)
    if coll is None or coll.get("_removed"):
        return None
    return coll


def _get_entity(snap: dict, coll_id: str, entity_id: str) -> tuple[dict | None, dict | None]:
    """Lookup a non-removed entity. Returns (collection, entity) or (None, None)."""
    coll = _get_collection(snap, coll_id)
    if coll is None:
        return None, None
    entity = coll["entities"].get(entity_id)
    if entity is None or entity.get("_removed"):
        return coll, None
    return coll, entity


def _validate_field_value(value: Any, field_type: str | dict) -> tuple[bool, str | None]:
    """
    Check if a value conforms to a schema field type.
    Returns (valid, error_message).
    """
    if value is None:
        if is_nullable_type(field_type):
            return True, None
        return False, "null not allowed for non-nullable type"

    bt = base_type(field_type)

    if bt == "string":
        return isinstance(value, str), "expected string"
    if bt == "int":
        return isinstance(value, int) and not isinstance(value, bool), "expected int"
    if bt == "float":
        return isinstance(value, int | float) and not isinstance(value, bool), "expected float"
    if bt == "bool":
        return isinstance(value, bool), "expected bool"
    if bt == "date":
        return isinstance(value, str), "expected date string"  # further validation could check ISO format
    if bt == "datetime":
        return isinstance(value, str), "expected datetime string"
    if bt == "enum":
        if isinstance(field_type, dict) and "enum" in field_type:
            return value in field_type["enum"], f"expected one of {field_type['enum']}"
        return False, "malformed enum type"
    if bt == "list":
        if not isinstance(value, list):
            return False, "expected list"
        if isinstance(field_type, dict) and "list" in field_type:
            inner = field_type["list"]
            for item in value:
                ok, _ = _validate_field_value(item, inner)
                if not ok:
                    return False, f"list item type mismatch: expected {inner}"
        return True, None

    return True, None  # Unknown types pass (forward compat)


def _check_constraints(snap: dict, event: Event, warnings: list[Warning]) -> bool:
    """
    Check relevant constraints after an event is applied.
    Returns False if a strict constraint was violated (event should be rejected).
    Adds warnings for non-strict violations.
    """
    for constraint in snap["constraints"]:
        rule = constraint.get("rule")
        strict = constraint.get("strict", False)
        violated = False
        msg = constraint.get("message", f"Constraint {constraint.get('id')} violated")

        if rule == "collection_max_entities" and event.type in ("entity.create",):
            coll_id = constraint.get("collection")
            max_val = constraint.get("value")
            if coll_id and max_val is not None:
                coll = _get_collection(snap, coll_id)
                if coll:
                    count = sum(1 for e in coll["entities"].values() if not e.get("_removed"))
                    if count > max_val:
                        violated = True

        elif rule == "unique_field" and event.type in ("entity.create", "entity.update"):
            coll_id = constraint.get("collection")
            field_name = constraint.get("field")
            if coll_id and field_name:
                coll = _get_collection(snap, coll_id)
                if coll:
                    values_seen: list[Any] = []
                    for ent in coll["entities"].values():
                        if ent.get("_removed"):
                            continue
                        val = ent.get(field_name)
                        if val is not None and val in values_seen:
                            violated = True
                            break
                        if val is not None:
                            values_seen.append(val)

        elif rule == "exclude_pair" and event.type == "relationship.set":
            # Two entities must NOT share the same target
            # Only check if this event involves one of the constrained entities
            rel_type = constraint.get("relationship_type")
            entities = constraint.get("entities", [])
            event_from = event.payload.get("from")
            event_rel_type = event.payload.get("type")

            if rel_type and len(entities) == 2 and event_rel_type == rel_type:
                # Only check if this event's "from" entity is one of the constrained entities
                if event_from in entities:
                    # Find what targets each entity has for this relationship type
                    targets: dict[str, str | None] = {e: None for e in entities}
                    for rel in snap["relationships"]:
                        if rel.get("_excluded"):
                            continue
                        if rel.get("type") == rel_type and rel.get("from") in targets:
                            targets[rel["from"]] = rel.get("to")
                    # If both entities have the same target, violated
                    target_vals = [t for t in targets.values() if t is not None]
                    if len(target_vals) == 2 and target_vals[0] == target_vals[1]:
                        violated = True

        elif rule == "require_same" and event.type == "relationship.set":
            # Two entities MUST share the same target
            # Only check if this event involves one of the constrained entities
            rel_type = constraint.get("relationship_type")
            entities = constraint.get("entities", [])
            event_from = event.payload.get("from")
            event_rel_type = event.payload.get("type")

            if rel_type and len(entities) == 2 and event_rel_type == rel_type:
                if event_from in entities:
                    targets: dict[str, str | None] = {e: None for e in entities}
                    for rel in snap["relationships"]:
                        if rel.get("_excluded"):
                            continue
                        if rel.get("type") == rel_type and rel.get("from") in targets:
                            targets[rel["from"]] = rel.get("to")
                    # Both must have a target and they must match
                    t1, t2 = targets.get(entities[0]), targets.get(entities[1])
                    if t1 is not None and t2 is not None and t1 != t2:
                        violated = True

        elif rule == "max_per_target" and event.type == "relationship.set":
            # No target can have more than N sources
            rel_type = constraint.get("relationship_type")
            max_val = constraint.get("value")
            if rel_type and max_val is not None:
                # Count sources per target
                target_counts: dict[str, int] = {}
                for rel in snap["relationships"]:
                    if rel.get("_excluded"):
                        continue
                    if rel.get("type") == rel_type:
                        to_ref = rel.get("to")
                        target_counts[to_ref] = target_counts.get(to_ref, 0) + 1
                # Check if any target exceeds max
                for count in target_counts.values():
                    if count > max_val:
                        violated = True
                        break

        elif rule == "min_per_target" and event.type == "relationship.set":
            # Check if any previously-populated target now drops below min
            rel_type = constraint.get("relationship_type")
            min_val = constraint.get("value")
            if rel_type and min_val is not None:
                # Count current sources for each target that this entity might have left
                target_counts: dict[str, int] = {}
                for rel in snap["relationships"]:
                    if rel.get("_excluded"):
                        continue
                    if rel.get("type") == rel_type:
                        to_ref = rel.get("to")
                        target_counts[to_ref] = target_counts.get(to_ref, 0) + 1
                # Check targets that had relationships before - if any dropped below min
                for _to_ref, count in target_counts.items():
                    if count < min_val:
                        violated = True
                        break

        elif rule == "required_fields" and event.type == "entity.update":
            # Check if any monitored field is being set to null
            coll_id = constraint.get("collection")
            req_fields = constraint.get("fields") or []
            if event.payload.get("ref"):
                ref_coll, _ = parse_ref(event.payload["ref"])
                if ref_coll == coll_id:
                    update_fields = event.payload.get("fields", {})
                    for field in req_fields:
                        if field in update_fields and update_fields[field] is None:
                            violated = True
                            break

        elif rule == "required_fields" and event.type == "field.remove":
            # Warn if removing a field referenced by required_fields constraint
            coll_id = constraint.get("collection")
            req_fields = constraint.get("fields") or []
            if event.payload.get("collection") == coll_id:
                if event.payload.get("name") in req_fields:
                    violated = True
                    msg = f"Removing field '{event.payload.get('name')}' referenced by required_fields constraint"

        if violated:
            if strict:
                return False  # Caller should reject
            warnings.append(Warning(code="CONSTRAINT_VIOLATED", message=msg))

    return True


# ---------------------------------------------------------------------------
# Primitive handlers
# ---------------------------------------------------------------------------


def _handle_entity_create(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["collection"]
    entity_id = p.get("id")
    fields = p.get("fields", {})
    warnings: list[Warning] = []

    # 1. Collection must exist
    coll = _get_collection(snap, coll_id)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

    # 2. Auto-generate ID if missing
    if entity_id is None:
        counter = len(coll["entities"]) + 1
        entity_id = f"{coll_id}_{counter}"
        while entity_id in coll["entities"]:
            counter += 1
            entity_id = f"{coll_id}_{counter}"

    # 3. Check ID doesn't already exist (unless re-creating removed entity)
    existing = coll["entities"].get(entity_id)
    if existing is not None and not existing.get("_removed"):
        return _reject(snap, "ENTITY_ALREADY_EXISTS", f"{coll_id}/{entity_id}")

    # 4. Validate fields against schema
    schema = coll.get("schema", {})
    entity_fields: dict[str, Any] = {}

    for field_name, field_type in schema.items():
        if field_name in fields:
            valid, err = _validate_field_value(fields[field_name], field_type)
            if not valid:
                return _reject(snap, "TYPE_MISMATCH", f"{field_name}: {err}")
            entity_fields[field_name] = fields[field_name]
        elif is_nullable_type(field_type):
            entity_fields[field_name] = None
        else:
            return _reject(snap, "REQUIRED_FIELD_MISSING", f"'{field_name}' is required")

    # Warn about extra fields not in schema
    for key in fields:
        if key not in schema:
            warnings.append(
                Warning(
                    code="UNKNOWN_FIELD_IGNORED",
                    message=f"Field '{key}' not in schema, ignored",
                )
            )

    # 5. Store entity
    entity_fields["_removed"] = False
    entity_fields["_created_seq"] = event.sequence
    coll["entities"][entity_id] = entity_fields

    # 6. Check constraints
    if not _check_constraints(snap, event, warnings):
        # Undo the creation for strict constraint violation
        del coll["entities"][entity_id]
        return _reject(snap, "STRICT_CONSTRAINT_VIOLATED", "entity.create violated strict constraint")

    return _ok(snap, warnings)


def _handle_entity_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    fields = p.get("fields", {})
    warnings: list[Warning] = []

    if "ref" in p:
        # Single entity update
        coll_id, entity_id = parse_ref(p["ref"])
        coll, entity = _get_entity(snap, coll_id, entity_id)
        if coll is None:
            return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)
        if entity is None:
            return _reject(snap, "ENTITY_NOT_FOUND", p["ref"])

        schema = coll.get("schema", {})
        for key, value in fields.items():
            if key in schema:
                valid, err = _validate_field_value(value, schema[key])
                if not valid:
                    return _reject(snap, "TYPE_MISMATCH", f"{key}: {err}")
            entity[key] = value

        entity["_updated_seq"] = event.sequence

    elif "filter" in p:
        # Bulk update via filter
        filt = p["filter"]
        coll_id = filt["collection"]
        where = filt.get("where", {})

        coll = _get_collection(snap, coll_id)
        if coll is None:
            return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

        schema = coll.get("schema", {})
        count = 0

        for entity in coll["entities"].values():
            if entity.get("_removed"):
                continue
            # Check filter match
            if all(entity.get(k) == v for k, v in where.items()):
                for key, value in fields.items():
                    if key in schema:
                        valid, err = _validate_field_value(value, schema[key])
                        if not valid:
                            return _reject(snap, "TYPE_MISMATCH", f"{key}: {err}")
                    entity[key] = value
                entity["_updated_seq"] = event.sequence
                count += 1

        warnings.append(
            Warning(
                code="ENTITIES_AFFECTED",
                message=f"{count} entities updated",
            )
        )

    # Check constraints
    if not _check_constraints(snap, event, warnings):
        return _reject(snap, "STRICT_CONSTRAINT_VIOLATED", "entity.update violated strict constraint")

    return _ok(snap, warnings)


def _handle_entity_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id, entity_id = parse_ref(p["ref"])
    warnings: list[Warning] = []

    coll = snap["collections"].get(coll_id)
    if coll is None or coll.get("_removed"):
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

    entity = coll["entities"].get(entity_id)
    if entity is None:
        return _reject(snap, "ENTITY_NOT_FOUND", p["ref"])

    if entity.get("_removed"):
        warnings.append(Warning(code="ALREADY_REMOVED", message=f"{p['ref']} already removed"))
        return _ok(snap, warnings)

    entity["_removed"] = True
    entity["_removed_seq"] = event.sequence

    # Exclude relationships involving this entity
    ref = p["ref"]
    for rel in snap["relationships"]:
        if rel.get("from") == ref or rel.get("to") == ref:
            rel["_excluded"] = True

    return _ok(snap, warnings)


def _handle_collection_create(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["id"]

    existing = snap["collections"].get(coll_id)
    if existing is not None and not existing.get("_removed"):
        return _reject(snap, "COLLECTION_ALREADY_EXISTS", coll_id)

    # Validate schema types
    schema = p.get("schema", {})
    for field_name, field_type in schema.items():
        if not is_valid_field_type(field_type):
            return _reject(snap, "TYPE_MISMATCH", f"Invalid schema type for '{field_name}': {field_type}")

    snap["collections"][coll_id] = {
        "id": coll_id,
        "name": p.get("name", coll_id.replace("_", " ").title()),
        "schema": schema,
        "settings": p.get("settings", {}),
        "entities": {},
        "_removed": False,
        "_created_seq": event.sequence,
    }

    return _ok(snap)


def _handle_collection_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["id"]

    coll = _get_collection(snap, coll_id)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

    if "name" in p:
        coll["name"] = p["name"]
    if "settings" in p:
        settings = coll.get("settings", {})
        for k, v in p["settings"].items():
            if v is None:
                settings.pop(k, None)
            else:
                settings[k] = v
        coll["settings"] = settings

    return _ok(snap)


def _handle_collection_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["id"]
    warnings: list[Warning] = []

    coll = snap["collections"].get(coll_id)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)
    if coll.get("_removed"):
        warnings.append(Warning(code="ALREADY_REMOVED", message=f"Collection '{coll_id}' already removed"))
        return _ok(snap, warnings)

    # Soft-delete collection and all entities
    coll["_removed"] = True
    for entity in coll["entities"].values():
        entity["_removed"] = True

    # Exclude relationships involving entities in this collection
    for rel in snap["relationships"]:
        if rel.get("from", "").startswith(f"{coll_id}/") or rel.get("to", "").startswith(f"{coll_id}/"):
            rel["_excluded"] = True

    # Remove views sourced from this collection
    for view in snap["views"].values():
        if view.get("source") == coll_id:
            view["_removed"] = True

    # Remove collection_view blocks referencing this collection
    blocks_to_remove = []
    for block_id, block in snap["blocks"].items():
        if block.get("type") == "collection_view":
            props = block.get("props", {})
            if props.get("source") == coll_id:
                blocks_to_remove.append(block_id)

    # Remove blocks from their parents and delete them
    for block_id in blocks_to_remove:
        block = snap["blocks"].get(block_id)
        if block:
            parent_id = block.get("parent", "block_root")
            parent = snap["blocks"].get(parent_id)
            if parent and block_id in parent.get("children", []):
                parent["children"].remove(block_id)
            del snap["blocks"][block_id]

    return _ok(snap, warnings)


def _handle_field_add(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["collection"]
    field_name = p["name"]
    field_type = p["type"]

    coll = _get_collection(snap, coll_id)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

    schema = coll.get("schema", {})
    if field_name in schema:
        return _reject(snap, "FIELD_ALREADY_EXISTS", f"'{field_name}' in '{coll_id}'")

    # Required field without default → reject (unless collection is empty)
    has_entities = any(not e.get("_removed") for e in coll["entities"].values())
    if not is_nullable_type(field_type) and "default" not in p and has_entities:
        return _reject(snap, "REQUIRED_FIELD_NO_DEFAULT", f"Can't add required field '{field_name}' without default")

    schema[field_name] = field_type

    # Backfill existing entities (including removed, for undo/replay support)
    default = p.get("default", None)
    for entity in coll["entities"].values():
        entity[field_name] = default

    return _ok(snap)


def _handle_field_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["collection"]
    field_name = p["name"]

    coll = _get_collection(snap, coll_id)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

    schema = coll.get("schema", {})
    if field_name not in schema:
        return _reject(snap, "FIELD_NOT_FOUND", f"'{field_name}' in '{coll_id}'")

    warnings: list[Warning] = []
    old_type = schema[field_name]

    # Handle type change
    if "type" in p:
        new_type = p["type"]

        # Type compatibility checking (before validity check for better error messages)
        old_base = base_type(old_type)

        # Handle bare "list" string (should be {"list": "type"})
        if new_type == "list" or (isinstance(new_type, dict) and "list" in new_type):
            if old_base in ("string", "bool", "date", "datetime", "int", "float", "enum"):
                return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", f"Cannot convert {old_base} to list")

        if not is_valid_field_type(new_type):
            return _reject(snap, "TYPE_MISMATCH", f"Invalid type: {new_type}")

        new_base = base_type(new_type)

        # Get existing non-null values
        existing_values = []
        for entity in coll["entities"].values():
            if entity.get("_removed"):
                continue
            val = entity.get(field_name)
            if val is not None:
                existing_values.append(val)

        # Check compatibility based on type transition
        if old_base == "enum" and new_base not in ("enum", "string"):
            # enum → anything other than string is rejected
            return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", f"Cannot convert enum to {new_base}")

        if old_base == "list":
            # list → anything else is rejected
            return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", f"Cannot convert list to {new_base}")

        if old_base == "float" and new_base == "int" and existing_values:
            # float → int: check for lossy conversion
            for val in existing_values:
                if isinstance(val, float) and val != int(val):
                    warnings.append(
                        Warning(
                            code="LOSSY_TYPE_CONVERSION",
                            message="Converting float to int will truncate decimal values",
                        )
                    )
                    break

        if old_base == "string" and new_base == "int" and existing_values:
            # string → int: check all values are numeric
            for val in existing_values:
                if isinstance(val, str):
                    try:
                        int(val)
                    except ValueError:
                        return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", f"Cannot convert '{val}' to int")

        if old_base == "string" and new_base == "enum" and existing_values:
            # string → enum: check all values are in enum
            if isinstance(new_type, dict) and "enum" in new_type:
                allowed = set(new_type["enum"])
                for val in existing_values:
                    if val not in allowed:
                        return _reject(
                            snap, "INCOMPATIBLE_TYPE_CHANGE", f"Value '{val}' not in enum {new_type['enum']}"
                        )

        if old_base in ("string", "bool", "date", "datetime") and new_base == "list":
            return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", f"Cannot convert {old_base} to list")

        if old_base == "date" and new_base == "int":
            return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", "Cannot convert date to int")

        if old_base == "bool" and new_base == "float":
            return _reject(snap, "INCOMPATIBLE_TYPE_CHANGE", "Cannot convert bool to float")

        schema[field_name] = new_type

    # Handle rename
    if "rename" in p:
        new_name = p["rename"]
        if new_name in schema:
            return _reject(snap, "FIELD_ALREADY_EXISTS", f"'{new_name}' in '{coll_id}'")
        schema[new_name] = schema.pop(field_name)
        for entity in coll["entities"].values():
            if field_name in entity:
                entity[new_name] = entity.pop(field_name)

    return _ok(snap, warnings)


def _handle_field_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    coll_id = p["collection"]
    field_name = p["name"]
    warnings: list[Warning] = []

    coll = _get_collection(snap, coll_id)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", coll_id)

    schema = coll.get("schema", {})
    if field_name not in schema:
        return _reject(snap, "FIELD_NOT_FOUND", f"'{field_name}' in '{coll_id}'")

    del schema[field_name]

    # Remove from all entities
    for entity in coll["entities"].values():
        entity.pop(field_name, None)

    # Warn about views referencing this field
    for view in snap["views"].values():
        if view.get("source") != coll_id:
            continue
        config = view.get("config", {})
        for config_key in ("show_fields", "hide_fields"):
            if field_name in config.get(config_key, []):
                config[config_key] = [f for f in config[config_key] if f != field_name]
                warnings.append(
                    Warning(
                        code="VIEW_FIELD_MISSING",
                        message=f"View '{view['id']}' referenced removed field '{field_name}'",
                    )
                )
        for config_key in ("sort_by", "group_by"):
            if config.get(config_key) == field_name:
                config.pop(config_key, None)
                warnings.append(
                    Warning(
                        code="VIEW_FIELD_MISSING",
                        message=f"View '{view['id']}' referenced removed field '{field_name}'",
                    )
                )

    # Check constraints (e.g., required_fields referencing this field)
    _check_constraints(snap, event, warnings)

    return _ok(snap, warnings)


def _handle_relationship_set(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    from_ref = p["from"]
    to_ref = p["to"]
    rel_type = p["type"]
    cardinality = p.get("cardinality", "many_to_one")
    data = p.get("data", {})

    # Resolve entities
    from_coll, from_ent = parse_ref(from_ref)
    to_coll, to_ent = parse_ref(to_ref)
    _, from_entity = _get_entity(snap, from_coll, from_ent)
    _, to_entity = _get_entity(snap, to_coll, to_ent)

    if from_entity is None:
        return _reject(snap, "ENTITY_NOT_FOUND", from_ref)
    if to_entity is None:
        return _reject(snap, "ENTITY_NOT_FOUND", to_ref)

    # Register or lookup relationship type
    if rel_type not in snap["relationship_types"]:
        snap["relationship_types"][rel_type] = {"cardinality": cardinality}
    stored_cardinality = snap["relationship_types"][rel_type]["cardinality"]

    # Enforce cardinality
    # many_to_one: many sources can point to one target, each source has only ONE target
    # one_to_one:  each source has one target AND each target has one source
    # many_to_many: no restrictions
    if stored_cardinality == "many_to_one":
        # Remove existing relationships from this source of this type (each source has one target)
        snap["relationships"] = [
            r
            for r in snap["relationships"]
            if not (r["from"] == from_ref and r["type"] == rel_type and not r.get("_excluded"))
        ]
    elif stored_cardinality == "one_to_one":
        # Remove both sides
        snap["relationships"] = [
            r
            for r in snap["relationships"]
            if not (
                (r["from"] == from_ref and r["type"] == rel_type and not r.get("_excluded"))
                or (r["to"] == to_ref and r["type"] == rel_type and not r.get("_excluded"))
            )
        ]
    # many_to_many: no auto-removal

    # Append new relationship
    snap["relationships"].append(
        {
            "from": from_ref,
            "to": to_ref,
            "type": rel_type,
            "data": data,
            "_seq": event.sequence,
        }
    )

    warnings: list[Warning] = []
    if not _check_constraints(snap, event, warnings):
        return _reject(snap, "STRICT_CONSTRAINT_VIOLATED", "relationship.set violated strict constraint")
    return _ok(snap, warnings)


def _handle_relationship_constrain(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    warnings: list[Warning] = []

    constraint = {
        "id": p["id"],
        "rule": p["rule"],
        "entities": p.get("entities"),
        "relationship_type": p.get("relationship_type"),
        "value": p.get("value"),
        "message": p.get("message"),
        "strict": p.get("strict", False),
    }

    # Replace if same ID exists, otherwise append
    existing_idx = None
    for i, c in enumerate(snap["constraints"]):
        if c.get("id") == p["id"]:
            existing_idx = i
            break
    if existing_idx is not None:
        snap["constraints"][existing_idx] = constraint
    else:
        snap["constraints"].append(constraint)

    return _ok(snap, warnings)


def _handle_block_set(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    block_id = p["id"]
    blocks = snap["blocks"]
    parent_id = p.get("parent", "block_root")
    position = p.get("position")

    existing = blocks.get(block_id)

    if existing is None:
        # CREATE mode
        if "type" not in p:
            return _reject(snap, "BLOCK_TYPE_MISSING", f"block.set (create) requires 'type' for '{block_id}'")
        if parent_id not in blocks:
            return _reject(snap, "BLOCK_NOT_FOUND", f"Parent '{parent_id}' not found")

        new_block = {
            "id": block_id,
            "type": p["type"],
            "parent": parent_id,
            "props": p.get("props", {}),
            "children": [],
        }
        blocks[block_id] = new_block

        # Insert into parent's children
        parent = blocks[parent_id]
        if position is not None and 0 <= position <= len(parent["children"]):
            parent["children"].insert(position, block_id)
        else:
            parent["children"].append(block_id)

    else:
        # UPDATE mode
        if "props" in p:
            existing_props = existing.get("props", {})
            existing_props.update(p["props"])
            existing["props"] = existing_props

        if "type" in p:
            existing["type"] = p["type"]

        # Handle reparenting
        if "parent" in p and p["parent"] != existing.get("parent"):
            old_parent_id = existing.get("parent", "block_root")
            new_parent_id = p["parent"]
            if new_parent_id not in blocks:
                return _reject(snap, "BLOCK_NOT_FOUND", f"Parent '{new_parent_id}' not found")

            # Remove from old parent
            old_parent = blocks.get(old_parent_id)
            if old_parent and block_id in old_parent["children"]:
                old_parent["children"].remove(block_id)

            # Insert into new parent
            new_parent = blocks[new_parent_id]
            if position is not None and 0 <= position <= len(new_parent["children"]):
                new_parent["children"].insert(position, block_id)
            else:
                new_parent["children"].append(block_id)

            existing["parent"] = new_parent_id

    return _ok(snap)


def _handle_block_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    block_id = p["id"]
    blocks = snap["blocks"]

    if block_id == "block_root":
        return _reject(snap, "CANT_REMOVE_ROOT", "Cannot remove block_root")

    if block_id not in blocks:
        return _reject(snap, "BLOCK_NOT_FOUND", block_id)

    # Collect block and all descendants
    to_remove: list[str] = []

    def collect(bid: str) -> None:
        to_remove.append(bid)
        block = blocks.get(bid)
        if block:
            for child in block.get("children", []):
                collect(child)

    collect(block_id)

    # Remove from parent
    block = blocks[block_id]
    parent_id = block.get("parent", "block_root")
    parent = blocks.get(parent_id)
    if parent and block_id in parent["children"]:
        parent["children"].remove(block_id)

    # Delete all collected blocks
    for bid in to_remove:
        blocks.pop(bid, None)

    return _ok(snap)


def _handle_block_reorder(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    parent_id = p["parent"]
    new_order = p["children"]
    blocks = snap["blocks"]
    warnings: list[Warning] = []

    if parent_id not in blocks:
        return _reject(snap, "BLOCK_NOT_FOUND", f"Parent '{parent_id}' not found")

    parent = blocks[parent_id]
    current_children = set(parent["children"])

    # Validate: warn about IDs not in current children
    valid_order: list[str] = []
    for cid in new_order:
        if cid in current_children:
            valid_order.append(cid)
        else:
            warnings.append(Warning(code="UNKNOWN_FIELD_IGNORED", message=f"'{cid}' is not a child of '{parent_id}'"))

    # Append any current children not in the provided order
    for cid in parent["children"]:
        if cid not in valid_order:
            valid_order.append(cid)

    parent["children"] = valid_order
    return _ok(snap, warnings)


def _handle_view_create(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    view_id = p["id"]
    warnings: list[Warning] = []

    if view_id in snap["views"]:
        return _reject(snap, "VIEW_ALREADY_EXISTS", view_id)

    source = p["source"]
    coll = _get_collection(snap, source)
    if coll is None:
        return _reject(snap, "COLLECTION_NOT_FOUND", source)

    # Warn about config referencing nonexistent schema fields
    config = p.get("config", {})
    schema = coll.get("schema", {})
    for field_ref_key in ("show_fields", "hide_fields"):
        for f in config.get(field_ref_key, []):
            if f not in schema:
                warnings.append(
                    Warning(code="VIEW_FIELD_MISSING", message=f"View '{view_id}' references field '{f}' not in schema")
                )

    snap["views"][view_id] = {
        "id": view_id,
        "type": p["type"],
        "source": source,
        "config": config,
    }

    return _ok(snap, warnings)


def _handle_view_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    view_id = p["id"]

    view = snap["views"].get(view_id)
    if view is None:
        return _reject(snap, "VIEW_NOT_FOUND", view_id)

    if "type" in p:
        view["type"] = p["type"]
    if "config" in p:
        existing_config = view.get("config", {})
        existing_config.update(p["config"])
        view["config"] = existing_config

    return _ok(snap)


def _handle_view_remove(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    view_id = p["id"]
    warnings: list[Warning] = []

    if view_id not in snap["views"]:
        return _reject(snap, "VIEW_NOT_FOUND", view_id)

    del snap["views"][view_id]

    # Null out block references to this view
    for block in snap["blocks"].values():
        if block.get("type") == "collection_view":
            props = block.get("props", {})
            if props.get("view") == view_id:
                props["view"] = None
                warnings.append(
                    Warning(
                        code="BLOCK_VIEW_MISSING", message=f"Block '{block['id']}' referenced removed view '{view_id}'"
                    )
                )

    return _ok(snap, warnings)


def _handle_style_set(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    for key, value in p.items():
        if value is None:
            snap["styles"].pop(key, None)
        else:
            snap["styles"][key] = value
    return _ok(snap)


def _handle_style_set_entity(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    ref = p["ref"]
    styles = p["styles"]

    coll_id, entity_id = parse_ref(ref)
    _, entity = _get_entity(snap, coll_id, entity_id)
    if entity is None:
        return _reject(snap, "ENTITY_NOT_FOUND", ref)

    existing_styles = entity.get("_styles", {})
    existing_styles.update(styles)
    entity["_styles"] = existing_styles

    return _ok(snap)


def _handle_meta_update(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    for key, value in p.items():
        snap["meta"][key] = value
    return _ok(snap)


def _handle_meta_annotate(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    snap["annotations"].append(
        {
            "note": p["note"],
            "pinned": p.get("pinned", False),
            "seq": event.sequence,
            "timestamp": event.timestamp,
        }
    )
    return _ok(snap)


def _handle_meta_constrain(snap: dict, event: Event) -> ReduceResult:
    p = event.payload
    warnings: list[Warning] = []

    constraint = {
        "id": p["id"],
        "rule": p["rule"],
        "collection": p.get("collection"),
        "field": p.get("field"),
        "fields": p.get("fields"),  # for required_fields constraint
        "value": p.get("value"),
        "message": p.get("message"),
        "strict": p.get("strict", False),
    }

    # Replace if same ID exists, otherwise append
    existing_idx = None
    for i, c in enumerate(snap["constraints"]):
        if c.get("id") == p["id"]:
            existing_idx = i
            break
    if existing_idx is not None:
        snap["constraints"][existing_idx] = constraint
    else:
        snap["constraints"].append(constraint)

    # Immediate validation
    if p["rule"] == "collection_max_entities":
        coll_id = p.get("collection")
        max_val = p.get("value")
        if coll_id and max_val is not None:
            coll = _get_collection(snap, coll_id)
            if coll:
                count = sum(1 for e in coll["entities"].values() if not e.get("_removed"))
                if count > max_val:
                    msg = p.get("message", f"Collection already has {count} entities (max {max_val})")
                    warnings.append(Warning(code="CONSTRAINT_VIOLATED", message=msg))

    if p["rule"] == "unique_field":
        coll_id = p.get("collection")
        field_name = p.get("field")
        if coll_id and field_name:
            coll = _get_collection(snap, coll_id)
            if coll:
                seen: set[Any] = set()
                for ent in coll["entities"].values():
                    if ent.get("_removed"):
                        continue
                    val = ent.get(field_name)
                    if val is not None and val in seen:
                        warnings.append(
                            Warning(
                                code="CONSTRAINT_VIOLATED",
                                message=p.get("message", f"Duplicate value for '{field_name}'"),
                            )
                        )
                        break
                    if val is not None:
                        seen.add(val)

    return _ok(snap, warnings)


# ---------------------------------------------------------------------------
# Handler dispatch table
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "entity.create": _handle_entity_create,
    "entity.update": _handle_entity_update,
    "entity.remove": _handle_entity_remove,
    "collection.create": _handle_collection_create,
    "collection.update": _handle_collection_update,
    "collection.remove": _handle_collection_remove,
    "field.add": _handle_field_add,
    "field.update": _handle_field_update,
    "field.remove": _handle_field_remove,
    "relationship.set": _handle_relationship_set,
    "relationship.constrain": _handle_relationship_constrain,
    "block.set": _handle_block_set,
    "block.remove": _handle_block_remove,
    "block.reorder": _handle_block_reorder,
    "view.create": _handle_view_create,
    "view.update": _handle_view_update,
    "view.remove": _handle_view_remove,
    "style.set": _handle_style_set,
    "style.set_entity": _handle_style_set_entity,
    "meta.update": _handle_meta_update,
    "meta.annotate": _handle_meta_annotate,
    "meta.constrain": _handle_meta_constrain,
}
