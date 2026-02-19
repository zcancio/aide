"""
JSONL stream parser for LLM output.

Buffers streaming text until newlines, expands field abbreviations,
and skips malformed lines with a warning.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Abbreviation expansion map — matches golden file format
_ABBREV: dict[str, str] = {
    "t": "type",
    "p": "props",
    "id": "id",  # kept for clarity — no change
}

# Nested abbreviations inside the props/payload dict
_PROP_ABBREV: dict[str, str] = {
    # Common abbreviated field names in golden files
    # (most props are already expanded; this handles any nested shorthands)
}


class JSONLParser:
    """
    Parses streaming JSONL from LLM output.

    Accumulates partial chunks in a buffer, emits complete parsed lines
    as they become available. Skips malformed JSON with a warning log.
    """

    def __init__(self) -> None:
        self.buffer = ""

    def feed(self, chunk: str) -> list[dict]:
        """
        Feed a text chunk (may be partial), return any complete parsed lines.

        Args:
            chunk: Raw text from the LLM stream

        Returns:
            List of expanded event dicts for each complete JSONL line
        """
        self.buffer += chunk
        lines = []
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
                lines.append(self.expand_abbreviations(parsed))
            except json.JSONDecodeError:
                logger.warning("JSONLParser: skipping malformed line: %r", stripped[:200])
        return lines

    def flush(self) -> list[dict]:
        """
        Flush any remaining content in the buffer as a final line.

        Call this after the stream ends to handle files with no trailing newline.

        Returns:
            List of expanded event dicts (0 or 1 items)
        """
        stripped = self.buffer.strip()
        self.buffer = ""
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            return [self.expand_abbreviations(parsed)]
        except json.JSONDecodeError:
            logger.warning("JSONLParser: skipping malformed final chunk: %r", stripped[:200])
            return []

    @staticmethod
    def expand_abbreviations(event: dict) -> dict:
        """
        Expand abbreviated field names to their full forms.

        Mappings:
          t  → type
          p  → props
          id → id  (identity, no change)

        Args:
            event: Raw parsed dict from JSONL line

        Returns:
            Dict with abbreviated keys expanded to full names
        """
        expanded: dict = {}
        for key, value in event.items():
            full_key = _ABBREV.get(key, key)
            expanded[full_key] = value

        # Rename "props" to "payload" so the reducer receives the expected field name
        if "props" in expanded and "payload" not in expanded:
            expanded["payload"] = expanded.pop("props")

        return expanded
