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
    Resolve a grid cell reference to an entity ref (e.g., "squares/cell_4_5").

    Supports multiple formats:
    - Numeric comma-separated: "0,0", "3,5", "9,9"
    - Numeric dash-separated: "0-0", "3-5"
    - Letter-based (when labels configured): "FU", "AQ"

    Args:
        cell_ref: User's cell reference
        collection: Collection ID (e.g., "squares")
        snapshot: Current aide snapshot with optional meta.col_labels and meta.row_labels

    Returns:
        GridResolution with entity_ref on success, error message on failure
    """
    cell_ref = cell_ref.strip()

    # Get grid dimensions from snapshot
    collections = snapshot.get("collections", {})
    coll = collections.get(collection, {})
    grid_config = coll.get("grid", {})
    rows = grid_config.get("rows", 10)
    cols = grid_config.get("cols", 10)

    meta = snapshot.get("meta", {})
    col_labels = meta.get("col_labels", [])
    row_labels = meta.get("row_labels", [])

    # Try numeric format first: "row,col" or "row-col" or "row_col"
    if "," in cell_ref or "-" in cell_ref or "_" in cell_ref:
        separator = "," if "," in cell_ref else ("-" if "-" in cell_ref else "_")
        parts = cell_ref.split(separator)
        if len(parts) == 2:
            try:
                row_index = int(parts[0].strip())
                col_index = int(parts[1].strip())

                # Validate bounds
                if 0 <= row_index < rows and 0 <= col_index < cols:
                    entity_ref = f"{collection}/cell_{row_index}_{col_index}"
                    return GridResolution(success=True, entity_ref=entity_ref)
                else:
                    return GridResolution(
                        success=False,
                        error=f"Cell {cell_ref} out of bounds. Grid is {rows}x{cols} (0-{rows - 1}, 0-{cols - 1}).",
                    )
            except ValueError:
                pass  # Not numeric, try label-based below

    # If no custom labels configured, require explicit row,col format
    if not col_labels or not row_labels:
        return GridResolution(
            success=False,
            error=f"Invalid cell reference: {cell_ref}. Use row,col format (e.g., 0,0 or 3,5).",
        )

    # Label-based resolution
    cell_ref = cell_ref.upper()

    if len(cell_ref) < 2:
        return GridResolution(
            success=False,
            error=f"Invalid cell reference: {cell_ref}",
        )

    # Find which character belongs to which axis
    col_index: int | None = None
    row_index: int | None = None

    col_range = f"{col_labels[0]}-{col_labels[-1]}" if col_labels else ""
    row_range = f"{row_labels[0]}-{row_labels[-1]}" if row_labels else ""

    for char in cell_ref:
        if char in col_labels:
            if col_index is not None:
                return GridResolution(
                    success=False,
                    error=f"No square {cell_ref}. Grid is {col_range} x {row_range}.",
                )
            col_index = col_labels.index(char)
        elif char in row_labels:
            if row_index is not None:
                return GridResolution(
                    success=False,
                    error=f"No square {cell_ref}. Grid is {col_range} x {row_range}.",
                )
            row_index = row_labels.index(char)
        else:
            return GridResolution(
                success=False,
                error=f"No square {cell_ref}. Grid is {col_range} x {row_range}.",
            )

    if col_index is None or row_index is None:
        return GridResolution(
            success=False,
            error=f"No square {cell_ref}. Grid is {col_range} x {row_range}.",
        )

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

            resolved.append(
                {
                    "type": p_type,
                    "payload": new_payload,
                }
            )
        else:
            # No cell_ref, pass through unchanged
            resolved.append(primitive)

    return ResolveResult(
        primitives=resolved,
        query_response=". ".join(query_responses) if query_responses else None,
    )
