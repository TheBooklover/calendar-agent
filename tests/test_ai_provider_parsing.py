"""
Tests for AI provider parsing.

We test that JSON text is converted into AIPlanningProposal deterministically.
"""

from calendar_agent.planning.ai_contract import AIPlanningProposal
from calendar_agent.planning.ai_provider import parse_ai_proposal_json


def test_parse_ai_proposal_json_success():
    text = '{"priority_order": ["Admin", "Deep Work"], "rationale": "Admin first.", "confidence": 0.8}'
    proposal = parse_ai_proposal_json(text)
    assert isinstance(proposal, AIPlanningProposal)
    assert proposal.priority_order == ["Admin", "Deep Work"]
    assert proposal.rationale == "Admin first."
    assert proposal.confidence == 0.8
