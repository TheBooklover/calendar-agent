"""
calendar_agent/planning/ai_factory.py

Build an AI reasoner (callable) if environment is configured.

In this project:
- propose_ai_planning_proposal(goals, model=...) returns AIPlanningProposal
- Orchestrator accepts a callable reasoner
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

Intervals = Sequence[Any]
Goals = Sequence[Tuple[str, int]]


def build_ai_reasoner() -> Optional[Callable[..., Any]]:
    """
    Returns:
        A callable reasoner if OPENAI_API_KEY is set,
        otherwise None (safe fallback).
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

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
        # Your reasoner currently only uses goals + model.
        # Everything else is intentionally ignored for now.
        return propose_ai_planning_proposal(
            goals=list(goals),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        )

    return _reasoner
