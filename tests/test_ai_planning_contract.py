"""
Tests for AI planning contract validation.

These tests ensure:
- AI output is treated as untrusted input
- Invalid proposals are rejected deterministically
"""

from calendar_agent.planning.ai_contract import AIPlanningProposal
from calendar_agent.planning.ai_validate import validate_ai_planning_proposal


def test_valid_proposal_passes():
    proposal = AIPlanningProposal(
        priority_order=["Admin", "Deep Work"],
        rationale="Handle admin first to unblock follow-ups, then focus time.",
        confidence=0.8,
    )
    ok, reason = validate_ai_planning_proposal(proposal, goal_labels=["Deep Work", "Admin"])
    assert ok is True
    assert reason == ""


def test_unknown_label_rejected():
    proposal = AIPlanningProposal(
        priority_order=["Exercise"],
        rationale="Because reasons.",
        confidence=0.9,
    )
    ok, reason = validate_ai_planning_proposal(proposal, goal_labels=["Deep Work", "Admin"])
    assert ok is False
    assert reason == "unknown_label_in_priority_order"


def test_low_confidence_rejected():
    proposal = AIPlanningProposal(
        priority_order=["Admin"],
        rationale="Not sure.",
        confidence=0.1,
    )
    ok, reason = validate_ai_planning_proposal(proposal, goal_labels=["Deep Work", "Admin"])
    assert ok is False
    assert reason == "confidence_below_threshold"


def test_missing_rationale_rejected():
    proposal = AIPlanningProposal(
        priority_order=["Admin"],
        rationale="   ",
        confidence=0.9,
    )
    ok, reason = validate_ai_planning_proposal(proposal, goal_labels=["Deep Work", "Admin"])
    assert ok is False
    assert reason == "missing_rationale"
