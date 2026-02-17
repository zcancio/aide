"""Grid cell reference resolver — converts cell labels to entity refs."""

from dataclasses import dataclass
from typing import Any


@dataclass
class GridResolution:
    """Result of resolving a grid cell reference."""

    success: bool
    entity_ref: str | None = None
    error: str | None = None


def resolve_grid_cell(
    cell_ref: str,
    collection: str,
    snapshot: dict[str, Any],
) -> GridResolution:
    """
    Resolve a grid cell reference (e.g., "FU") to an entity ref (e.g., "squares/cell_4_5").

    Args:
        cell_ref: User's cell reference like "FU", "AQ", "JZ"
        collection: Collection ID (e.g., "squares")
        snapshot: Current aide snapshot with meta.col_labels and meta.row_labels

    Returns:
        GridResolution with entity_ref on success, error message on failure
    """
    meta = snapshot.get("meta", {})
    col_labels = meta.get("col_labels", [])
    row_labels = meta.get("row_labels", [])

    if not col_labels or not row_labels:
        return GridResolution(
            success=False,
            error="Grid labels not configured.",
        )

    # Normalize to uppercase
    cell_ref = cell_ref.upper().strip()

    if len(cell_ref) < 2:
        return GridResolution(
            success=False,
            error=f"Invalid cell reference: {cell_ref}",
        )

    # Find which character belongs to which axis
    col_index: int | None = None
    row_index: int | None = None
    col_char: str | None = None
    row_char: str | None = None

    col_range = f"{col_labels[0]}-{col_labels[-1]}" if col_labels else ""
    row_range = f"{row_labels[0]}-{row_labels[-1]}" if row_labels else ""

    for char in cell_ref:
        if char in col_labels:
            if col_index is not None:
                # Already found a column char - invalid
                return GridResolution(
                    success=False,
                    error=f"No square {cell_ref}. Grid is {col_range} × {row_range}.",
                )
            col_index = col_labels.index(char)
            col_char = char
        elif char in row_labels:
            if row_index is not None:
                # Already found a row char - invalid
                return GridResolution(
                    success=False,
                    error=f"No square {cell_ref}. Grid is {col_range} × {row_range}.",
                )
            row_index = row_labels.index(char)
            row_char = char
        else:
            # Character not in either axis
            return GridResolution(
                success=False,
                error=f"No square {cell_ref}. Grid is {col_range} × {row_range}.",
            )

    if col_index is None or row_index is None:
        return GridResolution(
            success=False,
            error=f"No square {cell_ref}. Grid is {col_range} × {row_range}.",
        )

    # Build entity ref: collection/cell_{row}_{col}
    entity_ref = f"{collection}/cell_{row_index}_{col_index}"

    return GridResolution(
        success=True,
        entity_ref=entity_ref,
    )


@dataclass
class ResolveResult:
    """Result of resolving primitives."""

    primitives: list[dict[str, Any]]
    error: str | None = None
    query_response: str | None = None  # Response text from grid queries


def resolve_primitives(
    primitives: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> ResolveResult:
    """
    Post-process primitives to resolve any grid cell references and queries.

    Args:
        primitives: List of primitive dicts from L2/L3
        snapshot: Current aide snapshot

    Returns:
        ResolveResult with resolved primitives, optional error, and optional query response
    """
    resolved = []
    query_responses = []

    for primitive in primitives:
        p_type = primitive.get("type", "")
        payload = primitive.get("payload", {})

        # Handle grid.query - lookup cell value
        if p_type == "grid.query":
            cell_ref = payload.get("cell_ref", "")
            collection = payload.get("collection", "squares")
            field = payload.get("field", "owner")

            resolution = resolve_grid_cell(cell_ref, collection, snapshot)
            if not resolution.success:
                return ResolveResult(primitives=[], error=resolution.error)

            # Look up the entity value
            # Entity ref is like "squares/cell_4_5"
            coll_id, entity_id = resolution.entity_ref.split("/", 1)
            collections = snapshot.get("collections", {})
            coll = collections.get(coll_id, {})
            entities = coll.get("entities", {})
            entity = entities.get(entity_id, {})
            value = entity.get(field)

            if value:
                query_responses.append(f"{cell_ref.upper()}: {value}")
            else:
                query_responses.append(f"{cell_ref.upper()}: empty")

            # Don't add query to resolved primitives - it's read-only
            continue

        # Check if this primitive has a cell_ref that needs resolution
        if "cell_ref" in payload:
            cell_ref = payload["cell_ref"]
            collection = payload.get("collection", "squares")

            resolution = resolve_grid_cell(cell_ref, collection, snapshot)

            if not resolution.success:
                return ResolveResult(primitives=[], error=resolution.error)

            # Transform payload: remove cell_ref, add ref
            new_payload = {k: v for k, v in payload.items() if k not in ("cell_ref", "collection")}
            new_payload["ref"] = resolution.entity_ref

            resolved.append({
                "type": p_type,
                "payload": new_payload,
            })
        else:
            # No cell_ref, pass through unchanged
            resolved.append(primitive)

    return ResolveResult(
        primitives=resolved,
        query_response=". ".join(query_responses) if query_responses else None,
    )
