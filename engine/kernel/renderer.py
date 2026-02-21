"""
AIde Kernel — Query Helpers

Pure functions for resolving view entities and fields from snapshot state.
React handles all rendering; this module provides query utilities.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Query Helpers
# ---------------------------------------------------------------------------


def apply_sort(entities: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Sort entities by a field specified in view config."""
    sort_by = cfg.get("sort_by")
    if not sort_by:
        return entities
    reverse = cfg.get("sort_order") == "desc"

    def sort_key(e: dict[str, Any]) -> tuple[int, Any]:
        val = e.get(sort_by)
        if val is None:
            return (1, "")
        return (0, val)

    return sorted(entities, key=sort_key, reverse=reverse)


def apply_filter(entities: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter entities by field values specified in view config."""
    filter_cfg = cfg.get("filter")
    if not filter_cfg:
        return entities
    return [e for e in entities if all(e.get(k) == v for k, v in filter_cfg.items())]


def resolve_view_entities(snapshot: dict[str, Any], view_id: str) -> list[dict[str, Any]]:
    """Get entities for a view with sorting and filtering applied."""
    views = snapshot.get("views", {})
    view = views.get(view_id)
    if not view:
        return []
    collections = snapshot.get("collections", {})
    coll = collections.get(view.get("source", ""))
    if not coll or coll.get("_removed"):
        return []
    entities = [e for e in coll.get("entities", {}).values() if not e.get("_removed")]
    cfg = view.get("config", {})
    entities = apply_sort(entities, cfg)
    entities = apply_filter(entities, cfg)
    return entities


def resolve_view_fields(snapshot: dict[str, Any], view_id: str) -> list[str]:
    """Get visible fields for a view."""
    views = snapshot.get("views", {})
    view = views.get(view_id)
    if not view:
        return []
    collections = snapshot.get("collections", {})
    coll = collections.get(view.get("source", ""))
    if not coll or coll.get("_removed"):
        return []
    cfg = view.get("config", {})
    if "show_fields" in cfg:
        return cfg["show_fields"]
    return [f for f in coll.get("schema", {}).keys() if not f.startswith("_")]
