"""
AI Reasoner (V0.7)

Turns planning inputs into an AIPlanningProposal by:
- building a prompt
- calling LLM (JSON-only)
- parsing JSON into AIPlanningProposal

Important:
- Does NOT validate (validation is separate and deterministic).
"""

from __future__ import annotations

from typing import List, Tuple

from calendar_agent.planning.ai_contract import AIPlanningProposal
from calendar_agent.planning.ai_llm_client import call_llm_json_only
from calendar_agent.planning.ai_provider import _build_prompt, parse_ai_proposal_json


def propose_ai_planning_proposal(
    goals: List[Tuple[str, int]],
    *,
    model: str = "gpt-4.1-mini",
) -> AIPlanningProposal:
    """
    Ask LLM for a proposal (untrusted).

    Returns:
        AIPlanningProposal parsed from LLM JSON output
    """
    prompt = _build_prompt(goals)
    raw = call_llm_json_only(prompt, model=model)
    return parse_ai_proposal_json(raw)
