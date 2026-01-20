"""
Tests for PlanningPreferences (soft constraints).

Goal:
- Preferences should influence ordering (priority), but not violate hard constraints.
"""

from datetime import datetime

from calendar_agent.planner import Interval, propose_blocks
from calendar_agent.planning.preferences import PlanningPreferences


def test_priority_order_changes_first_block_label():
    # Single free slot: enough time to schedule at least one block
    free = [
        Interval(
            start=datetime(2026, 1, 20, 9, 0),
            end=datetime(2026, 1, 20, 11, 0),
        )
    ]

    goals = [("Deep Work", 60), ("Admin", 30)]

    # Baseline: input order = priority
    baseline = propose_blocks(free=free, goals=goals, buffer_minutes=10)
    assert baseline, "Expected at least one proposed block"
    assert baseline[0]["label"] == "Deep Work"

    # Preferences: Admin should go first
    prefs = PlanningPreferences(priority_order=["Admin", "Deep Work"])
    preferred = propose_blocks(free=free, goals=goals, buffer_minutes=10, preferences=prefs)
    assert preferred, "Expected at least one proposed block"
    assert preferred[0]["label"] == "Admin"
