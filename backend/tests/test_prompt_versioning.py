"""
Test prompt versioning for eval A/B testing.

Prompts must support version parameter to test candidate prompts
against production baseline.
"""

from __future__ import annotations

import pytest

from backend.services.prompt_builder import build_system_blocks


def test_prompt_version_loading():
    """Prompt builder must support version parameter."""
    snapshot = {"meta": {}, "entities": {}}

    # Default loads current version
    current = build_system_blocks("L3", snapshot)

    # Can load specific version
    v1 = build_system_blocks("L3", snapshot, version="v1")

    # Both should return valid system blocks
    assert len(current) == 2  # Static + snapshot blocks
    assert len(v1) == 2
    assert current[0]["type"] == "text"
    assert v1[0]["type"] == "text"

    # Current should point to v1 (via symlink)
    assert current[0]["text"] == v1[0]["text"]


def test_prompt_version_nonexistent():
    """Loading nonexistent version should raise clear error."""
    snapshot = {"meta": {}, "entities": {}}

    with pytest.raises(FileNotFoundError):
        build_system_blocks("L3", snapshot, version="v999")


def test_prompt_version_all_tiers():
    """All tiers should support versioning."""
    snapshot = {"meta": {}, "entities": {}}

    for tier in ["L2", "L3", "L4"]:
        blocks = build_system_blocks(tier, snapshot, version="v1")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "text"
        assert len(blocks[0]["text"]) > 0
