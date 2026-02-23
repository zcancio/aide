"""HTML renderer service using display.js via Node subprocess."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def render_html(state: dict[str, Any], title: str | None = None) -> str:
    """
    Render an aide state snapshot to HTML using display.js.

    Args:
        state: The aide state snapshot (entities, rootIds, meta)
        title: Optional page title (defaults to state.meta.title or "AIde")

    Returns:
        Full HTML document as string

    Raises:
        RuntimeError: If rendering fails
    """
    if title is None:
        title = state.get("meta", {}).get("title") or "AIde"

    render_input = {"state": state, "title": title, "description": "", "footer": None, "updatedAt": None}

    # Path to render.js script
    render_script = Path(__file__).parent.parent.parent / "scripts" / "render.js"

    try:
        result = subprocess.run(  # noqa: S603
            ["node", str(render_script)],  # noqa: S607
            input=json.dumps(render_input),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Render failed: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Render timeout") from e
    except Exception as e:
        raise RuntimeError(f"Render error: {str(e)}") from e
