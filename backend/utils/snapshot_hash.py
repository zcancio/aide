"""Snapshot hashing utilities for reconciliation."""

import hashlib
import json
from typing import Any


def hash_snapshot(snapshot: dict[str, Any]) -> str:
    """
    Compute a deterministic hash of a snapshot for reconciliation.

    The hash is computed over the serialized JSON representation of the snapshot,
    allowing client and server to verify they're in sync.

    Args:
        snapshot: The snapshot dict to hash

    Returns:
        Hexadecimal hash string (first 16 characters of SHA-256)
    """
    # Sort keys for deterministic serialization
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    hash_obj = hashlib.sha256(serialized.encode("utf-8"))
    # Return first 16 hex chars for brevity (64 bits should be sufficient for collision detection)
    return hash_obj.hexdigest()[:16]
