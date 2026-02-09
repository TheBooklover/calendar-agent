"""
AI Provider (V0.7)

This module is responsible for obtaining an AIPlanningProposal.
In V0.7, the AI output is:
- parsed into AIPlanningProposal
- validated elsewhere (validator remains source of truth)

Design rule:
- This module may fail or return low-quality output.
- Callers must treat it as untrusted input.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from calendar_agent.planning.ai_contract import AIPlanningProposal


def _build_prompt(goals: List[Tuple[str, int]]) -> str:
    """
    Build a minimal prompt that asks the model to output ONLY JSON.

    Note: Keep this prompt stable to support deterministic testing and regression checks.
    """
    goal_lines = "\n".join([f"- {label}: {minutes} minutes" for (label, minutes) in goals])

    return (
        "You are assisting with daily planning.\n"
        "Given the goals below, suggest a priority_order (list of labels).\n"
        "Return ONLY valid JSON with keys: priority_order, rationale, confidence.\n"
        "confidence must be a float between 0 and 1.\n\n"
        f"Goals:\n{goal_lines}\n"
    )


def parse_ai_proposal_json(text: str) -> AIPlanningProposal:
    """
    Parse AI JSON text into AIPlanningProposal.

    This does NOT validate contents beyond structural parsing.
    Validation is done by validate_ai_planning_proposal().
    """
    data = json.loads(text)

    # Defensive extraction with clear defaults / errors
    priority_order = data.get("priority_order")
    rationale = data.get("rationale", "")
    confidence = data.get("confidence", 0.0)

    return AIPlanningProposal(
        priority_order=priority_order,
        rationale=str(rationale),
        confidence=float(confidence),
    )
