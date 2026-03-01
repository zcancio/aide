"""
Tool definitions for AIde LLM calls.

Shared between eval and production. cache_control goes on the LAST tool
because Anthropic's prompt caching is prefix-based — the breakpoint must
come after all tools for them to be included in the cached prefix.

Both L3 and L4 receive the full tool set. L4 handles first-message schema
synthesis (needs mutate_entity, set_relationship) AND queries. The query-only
behavior is enforced by the L4 system prompt, not by withholding tools.
"""

TOOLS = [
    {
        "name": "mutate_entity",
        "description": "Create, update, remove, or move an entity in the page tree.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "remove", "move", "reorder"],
                },
                "id": {
                    "type": "string",
                    "description": "Entity ID (for create)",
                },
                "ref": {
                    "type": "string",
                    "description": "Entity ID (for update/remove/move)",
                },
                "parent": {
                    "type": "string",
                    "description": "'root' or parent entity ID",
                },
                "display": {
                    "type": "string",
                    "enum": [
                        "page", "section", "card", "list", "table",
                        "checklist", "grid", "metric", "text", "image",
                    ],
                },
                "props": {"type": "object"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "set_relationship",
        "description": "Set, remove, or constrain a relationship between entities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "remove", "constrain"],
                },
                "from": {"type": "string"},
                "to": {"type": "string"},
                "type": {"type": "string"},
                "cardinality": {
                    "type": "string",
                    "enum": ["one_to_one", "many_to_one", "many_to_many"],
                },
            },
            "required": ["action", "type"],
        },
    },
    {
        "name": "voice",
        "description": "Send a chat message to the user. You MUST call this tool in EVERY response — it is the ONLY way the user sees your reply. Without it, they see nothing. Call it after mutations to summarize, or alone for queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Short state reflection shown in chat. Max ~100 chars. No first person, no encouragement, no emojis.",
                },
            },
            "required": ["text"],
        },
        "cache_control": {"type": "ephemeral"},
    },
]
