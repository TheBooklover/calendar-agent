"""
Step 3.1 — A1 acceptance test for V0.5 planner

What this test proves:
- The planner can pack MULTIPLE blocks into the SAME free slot (V0.5 upgrade).
- Buffer is inserted BETWEEN blocks (not after the last block).
- Per-label minimum block overrides work (A1: Deep Work min = 30).
- NEW: The planner can PARTIALLY allocate a goal to make room for the next goal (slot-aware packing).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_agent.planner import Interval, propose_blocks


def test_v05_a1_packs_two_blocks_by_partially_allocating_first_goal():
    """
    A1 acceptance scenario (correct math):

    Free slot: 09:00–10:20 (80 minutes)
    Goals: Deep Work 60, Admin 30
    Buffer: 10 minutes

    Expected packing:
    - Deep Work: 09:00–09:40 (40)   <-- partial allocation to leave room
    - Buffer:   09:40–09:50 (10)   [implicit]
    - Admin:    09:50–10:20 (30)

    Deep Work has 20 minutes remaining unscheduled, which is expected with only one slot.
    """
    tz = ZoneInfo("America/Toronto")

    free = [
        Interval(
            start=datetime(2025, 12, 29, 9, 0, tzinfo=tz),
            end=datetime(2025, 12, 29, 10, 20, tzinfo=tz),
        )
    ]

    goals = [
        ("Deep Work", 60),
        ("Admin", 30),
    ]

    min_blocks = {
        "Deep Work": 30,  # A1 override
        "Admin": 30,
    }

    proposals = propose_blocks(
        free=free,
        goals=goals,
        buffer_minutes=10,
        min_block_minutes_by_label=min_blocks,
    )

    assert len(proposals) == 2, f"Expected 2 blocks, got {len(proposals)}: {proposals}"

    assert proposals[0]["label"] == "Deep Work"
    assert proposals[0]["minutes"] == 40
    assert proposals[0]["start"] == "2025-12-29T09:00:00-05:00"
    assert proposals[0]["end"] == "2025-12-29T09:40:00-05:00"

    assert proposals[1]["label"] == "Admin"
    assert proposals[1]["minutes"] == 30
    assert proposals[1]["start"] == "2025-12-29T09:50:00-05:00"
    assert proposals[1]["end"] == "2025-12-29T10:20:00-05:00"


def test_v05_is_deterministic_same_input_same_output():
    """
    Determinism test:
    Same inputs should yield the exact same outputs (ordering + timestamps).
    """
    tz = ZoneInfo("America/Toronto")

    free = [
        Interval(
            start=datetime(2025, 12, 29, 9, 0, tzinfo=tz),
            end=datetime(2025, 12, 29, 10, 20, tzinfo=tz),
        )
    ]
    goals = [("Deep Work", 60), ("Admin", 30)]
    min_blocks = {"Deep Work": 30, "Admin": 30}

    out1 = propose_blocks(free=free, goals=goals, buffer_minutes=10, min_block_minutes_by_label=min_blocks)
    out2 = propose_blocks(free=free, goals=goals, buffer_minutes=10, min_block_minutes_by_label=min_blocks)

    assert out1 == out2, f"Planner is not deterministic.\nFirst: {out1}\nSecond: {out2}"
def test_v05_without_a1_does_not_pack_admin_block():
    """
    Negative control:

    Same scenario as A1 test, but WITHOUT overriding Deep Work min block.

    Defaults:
    - Deep Work min = 60
    - Admin min = 30

    Expected behavior:
    - Deep Work consumes the slot first.
    - Only 20 minutes remain, which is < Admin min.
    - Result: ONLY Deep Work is scheduled.
    """
    tz = ZoneInfo("America/Toronto")

    free = [
        Interval(
            start=datetime(2025, 12, 29, 9, 0, tzinfo=tz),
            end=datetime(2025, 12, 29, 10, 20, tzinfo=tz),
        )
    ]

    goals = [
        ("Deep Work", 60),
        ("Admin", 30),
    ]

    # IMPORTANT: no min_block override here
    proposals = propose_blocks(
        free=free,
        goals=goals,
        buffer_minutes=10,
    )

    assert len(proposals) == 1, f"Expected only 1 block, got {len(proposals)}: {proposals}"

    assert proposals[0]["label"] == "Deep Work"
    assert proposals[0]["minutes"] == 60
    assert proposals[0]["start"] == "2025-12-29T09:00:00-05:00"
    assert proposals[0]["end"] == "2025-12-29T10:00:00-05:00"
