"""
AI Provider (V0.7+)

Responsibilities:
- Build the LLM prompt for planning proposals
- Parse LLM JSON into AIPlanningProposal

Design rule:
- AI output is untrusted.
- Validation happens elsewhere (deterministic validator is source of truth).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

from calendar_agent.planning.ai_contract import AIPlanningProposal


def _build_prompt(goals: List[Tuple[str, int]]) -> str:
    """
    Build a prompt that asks the model to output ONLY JSON.

    V1.0+: prompt wording is externalized under /prompts for versioning.
    """
    template_path = Path("prompts/planning_prompt_v1.txt")
    template = template_path.read_text(encoding="utf-8").strip()

    goal_lines = "\n".join([f"- {label}: {minutes} minutes" for (label, minutes) in goals])

    # Keep prompt construction deterministic and easy to diff
    prompt = (
        template
        + "\n\n"
        + "Goals:\n"
        + goal_lines
        + "\n\n"
        + "Return ONLY valid JSON matching the AIPlanningProposal schema."
    )
    return prompt


def parse_ai_proposal_json(text: str) -> AIPlanningProposal:
    """
    Parse AI JSON text into AIPlanningProposal.

    This does NOT validate contents beyond structural parsing.
    Validation is done by validate_ai_planning_proposal().
    """
    data = json.loads(text)

    # Defensive extraction with clear defaults
    priority_order = data.get("priority_order")
    rationale = data.get("rationale", "")
    confidence = data.get("confidence", 0.0)

    return AIPlanningProposal(
        priority_order=priority_order,
        rationale=str(rationale),
        confidence=float(confidence),
    )
