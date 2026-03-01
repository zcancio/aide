from backend.services.tool_defs import TOOLS


def test_tools_is_list():
    assert isinstance(TOOLS, list)
    assert len(TOOLS) >= 2  # voice + mutate_entity at minimum


def test_voice_tool_exists():
    names = [t["name"] for t in TOOLS]
    assert "voice" in names


def test_mutate_entity_tool_exists():
    names = [t["name"] for t in TOOLS]
    assert "mutate_entity" in names


def test_set_relationship_tool_exists():
    names = [t["name"] for t in TOOLS]
    assert "set_relationship" in names


def test_last_tool_has_cache_control():
    """Cache breakpoint goes on last tool for optimal cache ordering."""
    last = TOOLS[-1]
    assert "cache_control" in last
    assert last["cache_control"]["type"] == "ephemeral"


def test_all_tiers_get_full_tools():
    """Both L3 and L4 use the same TOOLS - L4 query behavior enforced by prompt."""
    names = [t["name"] for t in TOOLS]
    assert "voice" in names
    assert "mutate_entity" in names
    assert "set_relationship" in names
