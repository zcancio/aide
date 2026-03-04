"""
Test that evals use the same prompts as production.

This ensures prompt changes in backend/ automatically propagate to evals.
"""


def test_evals_use_backend_prompts():
    """Evals must use the same prompts as production."""
    import sys
    from pathlib import Path

    # Add backend to path
    backend_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(backend_root))

    from backend.services.prompt_builder import build_system_blocks as backend_build
    from evals.scripts.prompt_builder import build_system_blocks as eval_build

    snapshot = {"meta": {}, "entities": {}}

    # Test that evals delegate to backend (should be same function now)
    # After unification, eval_build IS backend_build
    assert eval_build is backend_build, "Evals must directly use backend's build_system_blocks"

    # Verify it works for L3 and L4 tiers
    for tier in ["L3", "L4"]:
        blocks = backend_build(tier, snapshot)
        assert len(blocks) == 2, f"{tier} should return 2 blocks (prompt + snapshot)"
        assert blocks[0]["type"] == "text"
        assert "cache_control" in blocks[0]
        assert blocks[1]["type"] == "text"
