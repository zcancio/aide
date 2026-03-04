"""
Tool utilities for converting between API tool calls and reducer events.

This module is kept dependency-free so it can be imported by both
the backend (streaming_orchestrator) and evals without triggering
the full backend import chain.
"""

from __future__ import annotations

import json
from typing import Any


def tool_use_to_reducer_event(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert a tool_use call to a reducer event.

    Maps:
      mutate_entity(action="create", ...) → {"t": "entity.create", ...}
      mutate_entity(action="update", ...) → {"t": "entity.update", ...}
      set_relationship(action="set", ...) → {"t": "rel.set", ...}
      voice(text="...") → {"t": "voice", "text": "..."}
    """
    if tool_name == "mutate_entity":
        action = tool_input.get("action", "")
        event: dict[str, Any] = {"t": f"entity.{action}"}

        # Map tool fields to reducer event fields
        if "id" in tool_input:
            event["id"] = tool_input["id"]
        if "ref" in tool_input:
            event["ref"] = tool_input["ref"]
        if "parent" in tool_input:
            event["parent"] = tool_input["parent"]
        if "display" in tool_input:
            event["display"] = tool_input["display"]

        # Handle props - also handle title directly for prompt compatibility
        props = tool_input.get("props", {})
        # Parse props if it's a JSON string
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except json.JSONDecodeError:
                props = {}
        if "title" in tool_input:
            props["title"] = tool_input["title"]
        if props:
            event["p"] = props

        return event

    elif tool_name == "set_relationship":
        action = tool_input.get("action", "set")
        event = {"t": f"rel.{action}"}

        for key in ("from", "to", "type", "cardinality"):
            if key in tool_input:
                event[key] = tool_input[key]

        return event

    elif tool_name == "voice":
        return {"t": "voice", "text": tool_input.get("text", "")}

    return None
