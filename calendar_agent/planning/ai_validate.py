"""
Validation for AIPlanningProposal (V0.7).

AI output is untrusted input.
If invalid, we ignore it and fall back to deterministic baseline.
"""

from __future__ import annotations

from typing import Iterable, Set, Tuple

from calendar_agent.planning.ai_contract import AIPlanningProposal


def validate_ai_planning_proposal(
    proposal: AIPlanningProposal,
    goal_labels: Iterable[str],
    *,
    min_confidence: float = 0.3,
    max_priority_items: int = 10,
) -> Tuple[bool, str]:
    """
    Returns (is_valid, reason_if_invalid).

    Rules:
    - confidence must be within [0, 1]
    - confidence must be >= min_confidence
    - rationale must be non-empty
    - priority_order labels must be a subset of goal_labels (if provided)
    - priority_order must not exceed max_priority_items (bounded change)
    """
    known: Set[str] = set(goal_labels)

    if not (0.0 <= proposal.confidence <= 1.0):
        return False, "confidence_out_of_range"

    if proposal.confidence < min_confidence:
        return False, "confidence_below_threshold"

    if not proposal.rationale or not proposal.rationale.strip():
        return False, "missing_rationale"

    if proposal.priority_order:
        if len(proposal.priority_order) > max_priority_items:
            return False, "priority_order_too_long"
        if any(label not in known for label in proposal.priority_order):
            return False, "unknown_label_in_priority_order"

    return True, ""
