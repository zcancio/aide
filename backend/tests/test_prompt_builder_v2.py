from datetime import datetime

from backend.services.prompt_builder import build_messages, build_system_blocks

# ── build_system_blocks ──────────────────────────────────────────────────────


def test_returns_two_blocks():
    blocks = build_system_blocks("L3", {"entities": {}})
    assert isinstance(blocks, list)
    assert len(blocks) == 2


def test_first_block_has_cache_control():
    blocks = build_system_blocks("L3", {"entities": {}})
    assert blocks[0]["type"] == "text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_second_block_has_no_cache_control():
    blocks = build_system_blocks("L3", {"entities": {}})
    assert "cache_control" not in blocks[1]


def test_snapshot_in_second_block_only():
    snap = {"entities": {"page": {"props": {"title": "Test"}}}}
    blocks = build_system_blocks("L3", snap)
    assert "Test" in blocks[1]["text"]
    assert "Test" not in blocks[0]["text"]


def test_current_date_injected():
    blocks = build_system_blocks("L3", {"entities": {}})
    today = datetime.now().strftime("%Y-%m-%d")
    assert today in blocks[0]["text"]
    assert "{{current_date}}" not in blocks[0]["text"]


def test_l4_static_clears_opus_cache_threshold():
    """Opus 4.5 requires >= 4,096 tokens before cache breakpoint.
    ~4 chars per token. 4,096 tokens ~ 16,384 chars.
    The static block (shared_prefix + tier prompt) must clear this."""
    blocks = build_system_blocks("L4", {"entities": {}})
    assert len(blocks[0]["text"]) >= 16_000, (
        f"L4 static block is {len(blocks[0]['text'])} chars, needs >= 16,000 to clear Opus 4,096-token cache threshold"
    )


def test_l3_static_clears_sonnet_cache_threshold():
    """Sonnet 4.5 requires >= 1,024 tokens. ~4,096 chars."""
    blocks = build_system_blocks("L3", {"entities": {}})
    assert len(blocks[0]["text"]) >= 4_000


def test_l3_and_l4_share_prefix():
    """Both tiers include the same shared_prefix text."""
    l3 = build_system_blocks("L3", {"entities": {}})
    l4 = build_system_blocks("L4", {"entities": {}})
    # Both should contain the shared prefix marker
    assert "# aide-prompt-v3.0 — Shared Prefix" in l3[0]["text"]
    assert "# aide-prompt-v3.0 — Shared Prefix" in l4[0]["text"]
    # Extract shared prefix section (everything after the tier header until "## Your Tier")
    l3_shared = l3[0]["text"].split("## Your Tier")[0]
    l4_shared = l4[0]["text"].split("## Your Tier")[0]
    # The shared prefix portions should contain the same core text
    assert "You are AIde — infrastructure" in l3_shared
    assert "You are AIde — infrastructure" in l4_shared


# ── build_messages (windowing) ───────────────────────────────────────────────


def test_windows_long_conversation():
    """Conversations longer than 9 messages get windowed."""
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"} for i in range(20)]
    result = build_messages(msgs, "current")
    # 9 history + 1 current = 10 max
    assert len(result) <= 10


def test_window_starts_on_user_role():
    """Windowed messages must start with a user message (API requirement)."""
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"} for i in range(20)]
    result = build_messages(msgs, "current")
    assert result[0]["role"] == "user"


def test_short_conversation_unchanged():
    """Short conversations pass through unwindowed."""
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    result = build_messages(msgs, "current")
    assert len(result) == 3
    assert result[0]["content"] == "hello"


def test_current_message_always_last():
    msgs = [{"role": "user", "content": "old"}]
    result = build_messages(msgs, "new")
    assert result[-1]["content"] == "new"
    assert result[-1]["role"] == "user"
