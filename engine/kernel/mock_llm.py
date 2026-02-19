"""
Mock LLM for deterministic testing and UX timing simulation.

Streams golden files line-by-line with configurable delays.
Used in tests (instant profile) and UX testing (realistic profiles).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "tests" / "fixtures" / "golden"

DELAY_PROFILES: dict[str, dict[str, int]] = {
    "instant": {"think_ms": 0, "per_line_ms": 0},
    "realistic_l2": {"think_ms": 300, "per_line_ms": 200},
    "realistic_l3": {"think_ms": 1500, "per_line_ms": 150},
    "slow": {"think_ms": 3000, "per_line_ms": 500},
}


class MockLLM:
    """Streams golden files line-by-line with configurable delays."""

    def __init__(self, golden_dir: Path = GOLDEN_DIR):
        self.golden_dir = golden_dir

    async def stream(
        self,
        scenario: str,
        profile: str = "instant",
    ) -> AsyncIterator[str]:
        """
        Stream a golden file line by line.

        Args:
            scenario: Golden file name without extension (e.g., "create_graduation")
            profile: Delay profile ("instant", "realistic_l2", "realistic_l3", "slow")

        Yields:
            Each non-empty line from the golden file

        Raises:
            FileNotFoundError: If the golden file does not exist
            ValueError: If the profile is not recognized
        """
        delays = DELAY_PROFILES.get(profile)
        if delays is None:
            raise ValueError(f"Unknown delay profile: {profile!r}. Valid profiles: {list(DELAY_PROFILES)}")

        path = self.golden_dir / f"{scenario}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Golden file not found: {path}")

        lines = path.read_text().splitlines()
        non_empty = [line for line in lines if line.strip()]

        # Think time before first line
        if delays["think_ms"] > 0:
            await asyncio.sleep(delays["think_ms"] / 1000)

        for i, line in enumerate(non_empty):
            yield line

            # Per-line delay after each line except the last
            if i < len(non_empty) - 1 and delays["per_line_ms"] > 0:
                await asyncio.sleep(delays["per_line_ms"] / 1000)

    def list_scenarios(self) -> list[str]:
        """Return names of all available golden file scenarios."""
        return sorted(p.stem for p in self.golden_dir.glob("*.jsonl"))
