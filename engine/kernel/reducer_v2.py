"""
AIde Kernel — v2 Reducer

Pure function: (snapshot, event) → ReduceResult

The v2 reducer handles the simplified JSONL event format used by the AI compiler.
Events use short-hand keys: t (type), p (props), ref, id, parent, display.

This is a rewrite of the v1 reducer with a flat entity hierarchy:
- No collections — entities are stored flat with parent references
- "root" is the implicit top-level parent
- entity.create with parent=None or parent="root" creates top-level entities

Reference: docs/program_management/PHASE_0B_REDUCER.md
"""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# ID validation
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _valid_id(value: str) -> bool:
    return bool(_ID_RE.match(value))


# ---------------------------------------------------------------------------
# Snapshot structure
# ---------------------------------------------------------------------------


def empty_snapshot() -> dict[str, Any]:
    """
    The initial snapshot for a v2 aide — zero events.

    Snapshot = {
        "meta":             {title, identity, annotations: [], constraints: {}},
        "entities":         {id: Entity},
        "relationships":    [{from, to, type, cardinality}],
        "rel_cardinalities":{rel_type: cardinality},
        "rel_constraints":  {constraint_id: Constraint},
        "styles":           {global: {}, entities: {}},
        "_sequence":        int,
    }
    """
    return {
        "meta": {
            "title": None,
            "identity": None,
            "annotations": [],
            "constraints": {},
        },
        "entities": {},
        "relationships": [],
        "rel_cardinalities": {},
        "rel_constraints": {},
        "styles": {
            "global": {},
            "entities": {},
        },
        "_sequence": 0,
    }


# ---------------------------------------------------------------------------
# ReduceResult
# ---------------------------------------------------------------------------


class ReduceResult:
    """
    Result of applying one v2 event to a snapshot.
    Never throws — always returns one of these.
    """

    __slots__ = ("snapshot", "accepted", "reason", "signal")

    def __init__(
        self,
        snapshot: dict[str, Any],
        accepted: bool,
        reason: str | None = None,
        signal: dict[str, Any] | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.accepted = accepted
        self.reason = reason
        self.signal = signal  # Populated for voice/escalate/batch signals

    def __repr__(self) -> str:  # pragma: no cover
        if self.accepted:
            return "ReduceResult(accepted=True)"
        return f"ReduceResult(accepted=False, reason={self.reason!r})"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _reject(snap: dict, reason: str) -> ReduceResult:
    return ReduceResult(snapshot=snap, accepted=False, reason=reason)


def _ok(snap: dict, signal: dict[str, Any] | None = None) -> ReduceResult:
    return ReduceResult(snapshot=snap, accepted=True, signal=signal)


def _inc(snap: dict) -> int:
    """Increment sequence counter and return new value."""
    snap["_sequence"] += 1
    return snap["_sequence"]


def _get_entity(snap: dict, entity_id: str) -> dict | None:
    """Return entity if it exists and is not removed."""
    e = snap["entities"].get(entity_id)
    if e is None or e.get("_removed"):
        return None
    return e


def _get_entity_raw(snap: dict, entity_id: str) -> dict | None:
    """Return entity regardless of _removed status."""
    return snap["entities"].get(entity_id)


def _get_ancestors(snap: dict, entity_id: str) -> set[str]:
    """Return set of all ancestor IDs (not including entity_id itself)."""
    ancestors: set[str] = set()
    current = snap["entities"].get(entity_id)
    while current is not None:
        parent = current.get("parent")
        if parent is None or parent == "root":
            break
        ancestors.add(parent)
        current = snap["entities"].get(parent)
    return ancestors


def _cascade_remove(snap: dict, entity_id: str, seq: int) -> None:
    """Recursively mark entity and all descendants as removed."""
    entity = snap["entities"].get(entity_id)
    if entity is None or entity.get("_removed"):
        return
    entity["_removed"] = True
    entity["_removed_seq"] = seq
    for child_id in list(entity.get("_children", [])):
        _cascade_remove(snap, child_id, seq)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def reduce(snapshot: dict[str, Any], event: dict[str, Any]) -> ReduceResult:
    """
    Apply one v2 event to the current snapshot.
    Returns ReduceResult with new snapshot + accepted flag.

    Pure function. Input snapshot is never modified (deep copy on mutation).
    """
    event_type = event.get("t")
    if event_type is None:
        return ReduceResult(snapshot=snapshot, accepted=False, reason="MISSING_TYPE: event has no 't' field")

    handler = _HANDLERS.get(event_type)
    if handler is None:
        return ReduceResult(
            snapshot=snapshot,
            accepted=False,
            reason=f"UNKNOWN_PRIMITIVE: {event_type}",
        )

    snap = copy.deepcopy(snapshot)
    return handler(snap, event)


def reduce_all(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Apply a sequence of events to a snapshot.
    Signals are accepted but don't mutate snapshot.
    Rejections are silently skipped.
    Returns the final snapshot.
    """
    for event in events:
        result = reduce(snapshot, event)
        if result.accepted:
            snapshot = result.snapshot
    return snapshot


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild snapshot from scratch by reducing over all events."""
    return reduce_all(empty_snapshot(), events)


# ---------------------------------------------------------------------------
# Entity primitives
# ---------------------------------------------------------------------------


def _handle_entity_create(snap: dict, event: dict) -> ReduceResult:
    entity_id = event.get("id")
    parent = event.get("parent", "root")
    display = event.get("display")
    props = event.get("p", {})

    # Validate ID
    if entity_id is None:
        return _reject(snap, "MISSING_ID: entity.create requires 'id'")
    if not _valid_id(entity_id):
        return _reject(snap, f"INVALID_ID: '{entity_id}' must be snake_case, max 64 chars")

    # Reject duplicate IDs
    existing = _get_entity_raw(snap, entity_id)
    if existing is not None and not existing.get("_removed"):
        return _reject(snap, f"ENTITY_EXISTS: '{entity_id}' already exists")

    # Validate parent
    if parent != "root":
        parent_entity = _get_entity(snap, parent)
        if parent_entity is None:
            return _reject(snap, f"PARENT_NOT_FOUND: '{parent}' does not exist or is removed")

    seq = _inc(snap)

    entity: dict[str, Any] = {
        "id": entity_id,
        "parent": parent,
        "display": display,
        "props": dict(props) if props else {},
        "_removed": False,
        "_children": [],
        "_created_seq": seq,
        "_updated_seq": seq,
    }

    snap["entities"][entity_id] = entity

    # Append to parent's _children
    if parent != "root":
        snap["entities"][parent]["_children"].append(entity_id)

    return _ok(snap)


def _handle_entity_update(snap: dict, event: dict) -> ReduceResult:
    ref = event.get("ref")
    props = event.get("p", {})

    if ref is None:
        return _reject(snap, "MISSING_REF: entity.update requires 'ref'")

    entity = _get_entity(snap, ref)
    if entity is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{ref}' does not exist or is removed")

    seq = _inc(snap)
    entity["props"].update(props)
    entity["_updated_seq"] = seq

    return _ok(snap)


def _handle_entity_remove(snap: dict, event: dict) -> ReduceResult:
    ref = event.get("ref")

    if ref is None:
        return _reject(snap, "MISSING_REF: entity.remove requires 'ref'")

    raw = _get_entity_raw(snap, ref)
    if raw is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{ref}' does not exist")

    if raw.get("_removed"):
        return _reject(snap, f"ALREADY_REMOVED: '{ref}' is already removed")

    seq = _inc(snap)
    _cascade_remove(snap, ref, seq)

    return _ok(snap)


def _handle_entity_move(snap: dict, event: dict) -> ReduceResult:
    ref = event.get("ref")
    new_parent = event.get("parent", "root")
    position = event.get("position")

    if ref is None:
        return _reject(snap, "MISSING_REF: entity.move requires 'ref'")

    entity = _get_entity(snap, ref)
    if entity is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{ref}' does not exist or is removed")

    # Reject move to self
    if new_parent == ref:
        return _reject(snap, f"CYCLE: cannot move '{ref}' to itself")

    # Reject move to own descendant (cycle prevention)
    if new_parent != "root":
        new_parent_entity = _get_entity(snap, new_parent)
        if new_parent_entity is None:
            return _reject(snap, f"PARENT_NOT_FOUND: '{new_parent}' does not exist or is removed")
        # Check if new_parent is a descendant of ref
        ancestors_of_new_parent = _get_ancestors(snap, new_parent)
        if ref in ancestors_of_new_parent or new_parent in _get_descendants(snap, ref):
            return _reject(snap, f"CYCLE: moving '{ref}' to '{new_parent}' would create a cycle")

    seq = _inc(snap)

    # Remove from old parent's _children
    old_parent = entity["parent"]
    if old_parent != "root":
        old_parent_entity = snap["entities"].get(old_parent)
        if old_parent_entity and ref in old_parent_entity["_children"]:
            old_parent_entity["_children"].remove(ref)

    # Insert into new parent's _children
    if new_parent != "root":
        children = snap["entities"][new_parent]["_children"]
        if position is not None and 0 <= position <= len(children):
            children.insert(position, ref)
        else:
            children.append(ref)

    entity["parent"] = new_parent
    entity["_updated_seq"] = seq

    return _ok(snap)


def _get_descendants(snap: dict, entity_id: str) -> set[str]:
    """Return set of all descendant IDs."""
    result: set[str] = set()
    entity = snap["entities"].get(entity_id)
    if entity is None:
        return result
    for child_id in entity.get("_children", []):
        result.add(child_id)
        result |= _get_descendants(snap, child_id)
    return result


def _handle_entity_reorder(snap: dict, event: dict) -> ReduceResult:
    ref = event.get("ref")
    new_children = event.get("children", [])

    if ref is None:
        return _reject(snap, "MISSING_REF: entity.reorder requires 'ref'")

    entity = _get_entity(snap, ref)
    if entity is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{ref}' does not exist or is removed")

    # Get current non-removed children
    current_children = [c for c in entity["_children"] if not snap["entities"].get(c, {}).get("_removed")]
    current_set = set(current_children)
    new_set = set(new_children)

    if new_set != current_set:
        missing = current_set - new_set
        extra = new_set - current_set
        parts = []
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        if extra:
            parts.append(f"extra: {sorted(extra)}")
        return _reject(snap, f"REORDER_MISMATCH: {', '.join(parts)}")

    seq = _inc(snap)
    # Preserve removed children at the end, maintain their order
    removed_children = [c for c in entity["_children"] if snap["entities"].get(c, {}).get("_removed")]
    entity["_children"] = list(new_children) + removed_children
    entity["_updated_seq"] = seq

    return _ok(snap)


# ---------------------------------------------------------------------------
# Relationship primitives
# ---------------------------------------------------------------------------


def _handle_rel_set(snap: dict, event: dict) -> ReduceResult:
    from_id = event.get("from")
    to_id = event.get("to")
    rel_type = event.get("type")
    cardinality = event.get("cardinality", "many_to_many")

    if from_id is None:
        return _reject(snap, "MISSING_FROM: rel.set requires 'from'")
    if to_id is None:
        return _reject(snap, "MISSING_TO: rel.set requires 'to'")
    if rel_type is None:
        return _reject(snap, "MISSING_TYPE: rel.set requires 'type'")

    from_entity = _get_entity(snap, from_id)
    if from_entity is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{from_id}' does not exist or is removed")

    to_entity = _get_entity(snap, to_id)
    if to_entity is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{to_id}' does not exist or is removed")

    # Register or use existing cardinality for this rel_type
    if rel_type not in snap["rel_cardinalities"]:
        snap["rel_cardinalities"][rel_type] = cardinality
    stored_cardinality = snap["rel_cardinalities"][rel_type]

    # Enforce cardinality
    if stored_cardinality == "many_to_one":
        # Remove existing relationships from from_id of this type
        snap["relationships"] = [
            r for r in snap["relationships"] if not (r["from"] == from_id and r["type"] == rel_type)
        ]
    elif stored_cardinality == "one_to_one":
        # Remove both sides
        snap["relationships"] = [
            r
            for r in snap["relationships"]
            if not ((r["from"] == from_id and r["type"] == rel_type) or (r["to"] == to_id and r["type"] == rel_type))
        ]
    # many_to_many: no auto-removal

    _inc(snap)
    snap["relationships"].append(
        {
            "from": from_id,
            "to": to_id,
            "type": rel_type,
            "cardinality": stored_cardinality,
        }
    )

    return _ok(snap)


def _handle_rel_remove(snap: dict, event: dict) -> ReduceResult:
    from_id = event.get("from")
    to_id = event.get("to")
    rel_type = event.get("type")

    # Idempotent — just remove matching relationships
    snap["relationships"] = [
        r
        for r in snap["relationships"]
        if not (
            (from_id is None or r["from"] == from_id)
            and (to_id is None or r["to"] == to_id)
            and (rel_type is None or r["type"] == rel_type)
        )
    ]
    _inc(snap)
    return _ok(snap)


def _handle_rel_constrain(snap: dict, event: dict) -> ReduceResult:
    constraint_id = event.get("id")
    if constraint_id is None:
        return _reject(snap, "MISSING_ID: rel.constrain requires 'id'")

    constraint = {
        "id": constraint_id,
        "rule": event.get("rule"),
        "entities": event.get("entities"),
        "rel_type": event.get("rel_type"),
        "value": event.get("value"),
        "message": event.get("message"),
        "strict": event.get("strict", False),
    }

    strict = event.get("strict", False)

    # Validate existing state if strict
    if strict and constraint.get("rule"):
        rule = constraint["rule"]
        entities = constraint.get("entities", [])
        rel_type = constraint.get("rel_type")

        if rule == "exclude_pair" and len(entities) == 2 and rel_type:
            # Check if both entities currently share the same target
            targets: dict[str, str | None] = {e: None for e in entities}
            for rel in snap["relationships"]:
                if rel.get("type") == rel_type and rel.get("from") in targets:
                    targets[rel["from"]] = rel.get("to")
            target_vals = [t for t in targets.values() if t is not None]
            if len(target_vals) == 2 and target_vals[0] == target_vals[1]:
                return _reject(snap, f"STRICT_CONSTRAINT_VIOLATED: existing state violates {constraint_id}")

    snap["rel_constraints"][constraint_id] = constraint
    _inc(snap)
    return _ok(snap)


# ---------------------------------------------------------------------------
# Style primitives
# ---------------------------------------------------------------------------


def _handle_style_set(snap: dict, event: dict) -> ReduceResult:
    props = event.get("p", {})
    snap["styles"]["global"].update(props)
    _inc(snap)
    return _ok(snap)


def _handle_style_entity(snap: dict, event: dict) -> ReduceResult:
    ref = event.get("ref")
    props = event.get("p", {})

    if ref is None:
        return _reject(snap, "MISSING_REF: style.entity requires 'ref'")

    entity = _get_entity(snap, ref)
    if entity is None:
        return _reject(snap, f"ENTITY_NOT_FOUND: '{ref}' does not exist or is removed")

    if "_styles" not in entity:
        entity["_styles"] = {}
    entity["_styles"].update(props)

    if ref not in snap["styles"]["entities"]:
        snap["styles"]["entities"][ref] = {}
    snap["styles"]["entities"][ref].update(props)

    _inc(snap)
    return _ok(snap)


# ---------------------------------------------------------------------------
# Meta primitives
# ---------------------------------------------------------------------------


def _handle_meta_set(snap: dict, event: dict) -> ReduceResult:
    props = event.get("p", {})
    for key, value in props.items():
        if key in ("title", "identity"):
            snap["meta"][key] = value
        else:
            snap["meta"][key] = value
    _inc(snap)
    return _ok(snap)


def _handle_meta_annotate(snap: dict, event: dict) -> ReduceResult:
    props = event.get("p", {})
    note = props.get("note", "")
    pinned = props.get("pinned", False)

    snap["meta"]["annotations"].append(
        {
            "note": note,
            "pinned": pinned,
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seq": snap["_sequence"],
        }
    )
    _inc(snap)
    return _ok(snap)


def _handle_meta_constrain(snap: dict, event: dict) -> ReduceResult:
    constraint_id = event.get("id")
    if constraint_id is None:
        return _reject(snap, "MISSING_ID: meta.constrain requires 'id'")

    constraint = {
        "id": constraint_id,
        "rule": event.get("rule"),
        "parent": event.get("parent"),
        "value": event.get("value"),
        "message": event.get("message"),
        "strict": event.get("strict", False),
    }

    strict = event.get("strict", False)

    # Validate existing state if strict
    if strict:
        rule = event.get("rule")
        parent = event.get("parent")
        value = event.get("value")

        if rule == "max_children" and parent is not None and value is not None:
            parent_entity = snap["entities"].get(parent)
            if parent_entity:
                active_children = [
                    c for c in parent_entity.get("_children", []) if not snap["entities"].get(c, {}).get("_removed")
                ]
                if len(active_children) > value:
                    msg = f"STRICT_CONSTRAINT_VIOLATED: {parent} has {len(active_children)} children (max {value})"
                    return _reject(snap, msg)

    snap["meta"]["constraints"][constraint_id] = constraint
    _inc(snap)
    return _ok(snap)


# ---------------------------------------------------------------------------
# Signal handlers (don't mutate snapshot)
# ---------------------------------------------------------------------------


def _handle_voice(snap: dict, event: dict) -> ReduceResult:
    """Voice signal — pass through for chat display. No snapshot mutation."""
    signal = {
        "type": "voice",
        "text": event.get("text", ""),
    }
    return _ok(snap, signal=signal)


def _handle_escalate(snap: dict, event: dict) -> ReduceResult:
    """Escalate signal — pass through for tier routing. No snapshot mutation."""
    signal = {
        "type": "escalate",
        "tier": event.get("tier"),
        "reason": event.get("reason"),
        "extract": event.get("extract"),
    }
    return _ok(snap, signal=signal)


def _handle_batch_start(snap: dict, event: dict) -> ReduceResult:
    """Batch start signal. No snapshot mutation."""
    signal = {"type": "batch.start"}
    return _ok(snap, signal=signal)


def _handle_batch_end(snap: dict, event: dict) -> ReduceResult:
    """Batch end signal. No snapshot mutation."""
    signal = {"type": "batch.end"}
    return _ok(snap, signal=signal)


# ---------------------------------------------------------------------------
# Handler dispatch table
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    # Entity primitives
    "entity.create": _handle_entity_create,
    "entity.update": _handle_entity_update,
    "entity.remove": _handle_entity_remove,
    "entity.move": _handle_entity_move,
    "entity.reorder": _handle_entity_reorder,
    # Relationship primitives
    "rel.set": _handle_rel_set,
    "rel.remove": _handle_rel_remove,
    "rel.constrain": _handle_rel_constrain,
    # Style primitives
    "style.set": _handle_style_set,
    "style.entity": _handle_style_entity,
    # Meta primitives
    "meta.set": _handle_meta_set,
    "meta.annotate": _handle_meta_annotate,
    "meta.constrain": _handle_meta_constrain,
    # Signals
    "voice": _handle_voice,
    "escalate": _handle_escalate,
    "batch.start": _handle_batch_start,
    "batch.end": _handle_batch_end,
}
