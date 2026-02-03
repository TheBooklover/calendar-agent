"""
Adapter layer: Convert a validated AIPlanningProposal into PlanningPreferences.

This is intentionally simple and deterministic.
"""

from __future__ import annotations

from calendar_agent.planning.ai_contract import AIPlanningProposal
from calendar_agent.planning.preferences import PlanningPreferences


def proposal_to_preferences(proposal: AIPlanningProposal) -> PlanningPreferences:
    """
    Convert AI proposal into PlanningPreferences.

    Assumes proposal has already been validated.
    """
    return PlanningPreferences(priority_order=proposal.priority_order)
