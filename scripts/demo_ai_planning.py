"""
scripts/demo_ai_planning.py

Portfolio demo:
- calls orchestrator
- shows baseline vs final
- demonstrates AI attempt/use once you wire ai_reasoner

For now, it runs deterministically and prints PlanResult.
"""

from __future__ import annotations

from calendar_agent.planning.orchestrator import plan_with_optional_ai


def main() -> None:
    # Minimal demo inputs
    free = []  # Later: populate with real intervals from calendar free/busy
    goals = [
        ("Deep Work", 120),
        ("Email", 30),
        ("Admin", 30),
    ]

    result = plan_with_optional_ai(
        free=free,
        goals=goals,
        buffer_minutes=10,
        enable_ai=False,  # flip once wired
        ai_reasoner=None, # wire later
    )

    print("AI attempted:", result.ai_attempted)
    print("AI used:", result.ai_used)
    print("Baseline blocks:", len(result.baseline_blocks))
    print("Final blocks:", len(result.final_blocks))


if __name__ == "__main__":
    main()
