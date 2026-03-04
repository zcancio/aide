"""
Prompt builder for evals — delegates to backend/services/prompt_builder.py.

This ensures evals use the same prompts as production. Any prompt changes
in backend/ automatically propagate to evals.
"""

import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

# Import and re-export backend prompt builder functions
from backend.services.prompt_builder import (
    build_system_blocks,
    build_messages,
    load_prompt,
    build_l2_prompt,
    build_l3_prompt,
    build_l4_prompt,
)

__all__ = [
    "build_system_blocks",
    "build_messages",
    "load_prompt",
    "build_l2_prompt",
    "build_l3_prompt",
    "build_l4_prompt",
]
