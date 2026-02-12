"""
calendar_agent/planning/ai_factory.py

Build an AI reasoner (callable) if environment is configured.

In this repo, the AI "reasoner" is function-based:
- propose_ai_planning_proposal(...) returns a structured proposal

The orchestrator supports callable reasoners, so we return a thin wrapper function.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

Intervals = Sequence[Any]
Goals = Sequence[Tuple[str, int]]


def build_ai_reasoner() -> Optional[Callable[..., Any]]:
    """
    Returns:
      - callable reasoner if OPENAI_API_KEY is set
      - None otherwise (safe fallback)
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    # Lazy import so CLI/tests work even when AI deps/config are absent
    from calendar_agent.planning.ai_reasoner import propose_ai_planning_proposal

    def _reasoner(
        *,
        free: Intervals,
        goals: Goals,
        buffer_minutes: int,
        min_block_minutes_by_label: Optional[Dict[str, int]] = None,
        preferences: Optional[Any] = None,
        baseline_blocks: Optional[Any] = None,
    ) -> Any:
        # Thin wrapper to match orchestrator's callable contract
        return propose_ai_planning_proposal(
            free=list(free),
            goals=list(goals),
            buffer_minutes=buffer_minutes,
            min_block_minutes_by_label=min_block_minutes_by_label,
            preferences=preferences,
            baseline_blocks=baseline_blocks,
        )

    return _reasoner
