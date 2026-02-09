"""
Manual smoke test for AI reasoner.

Run (from repo root):
  OPENAI_API_KEY=... python calendar_agent/smoke_ai_reasoner.py

This does NOT validate or plan—it's only:
- ask LLM for JSON proposal
- parse and print proposal
"""

from __future__ import annotations

from calendar_agent.planning.ai_reasoner import propose_ai_planning_proposal


def main() -> None:
    goals = [("Deep Work", 60), ("Admin", 30)]
    proposal = propose_ai_planning_proposal(goals)
    print(proposal)


if __name__ == "__main__":
    main()
