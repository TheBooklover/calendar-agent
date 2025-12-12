"""Smoke test: planning logic on top of FreeBusy (DEBUG + filtering + TZ normalization).

Reads:
- PLANNING_CALENDAR_IDS (comma-separated calendar IDs).

Behavior:
- If PLANNING_CALENDAR_IDS is set, ONLY those calendars are queried.
- If empty, ALL calendars are queried.

This version also:
- Plans a fixed target date (2025-12-15)
- Uses a wide window (04:00 → 22:00)
- Normalizes merged busy intervals to America/Toronto for sane printing/math

Run:
    python -u -m calendar_agent.smoke_planner
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_agent.google_auth import get_calendar_service
from calendar_agent.gcal_tools import list_calendars, freebusy_query
from calendar_agent import planner


def read_planning_calendar_ids() -> set[str]:
    """
    Parse PLANNING_CALENDAR_IDS from environment into a set.

    Example:
        "a,b,c" -> {"a","b","c"}
    """
    raw = os.getenv("PLANNING_CALENDAR_IDS", "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def main() -> None:
    # ---- Local timezone ----
    tz = ZoneInfo("America/Toronto")

    # ---- Planning calendars filter (optional) ----
    planning_ids = read_planning_calendar_ids()

    # ---- Target date (fixed for smoke test) ----
    # If you want "today" again later, we’ll swap this out for CLI args.
    target_date = datetime(2025, 12, 15, tzinfo=tz)

    # ---- Planning window (wide, as you tested) ----
    work_start = target_date.replace(hour=4, minute=0, second=0, microsecond=0)
    work_end = target_date.replace(hour=22, minute=0, second=0, microsecond=0)

    # ---- Auth + service ----
    service = get_calendar_service(["https://www.googleapis.com/auth/calendar"])

    # ---- Calendars inventory ----
    calendars = list_calendars(service)
    id_to_name = {c["id"]: c["summary"] for c in calendars}
    all_ids = [c["id"] for c in calendars if c.get("id")]

    # ---- Apply filter ----
    if planning_ids:
        calendar_ids = [cid for cid in all_ids if cid in planning_ids]
    else:
        calendar_ids = all_ids

    print("\n=== DEBUG: Env Var ===")
    print(f"PLANNING_CALENDAR_IDS={os.getenv('PLANNING_CALENDAR_IDS', '')!r}")

    print("\n=== DEBUG: Planning Calendars Used ===")
    if planning_ids:
        print("Filter ON (using only these calendars):")
    else:
        print("Filter OFF (using all calendars):")
    for cid in calendar_ids:
        print(f"- {id_to_name.get(cid, '(unknown)')} ({cid})")

    print("\n=== DEBUG: Planning Window (Local) ===")
    print(f"{work_start.isoformat()} → {work_end.isoformat()}")

    # ---- FreeBusy ----
    calendars_busy = freebusy_query(
        service=service,
        time_min=work_start.isoformat(),
        time_max=work_end.isoformat(),
        calendar_ids=calendar_ids,
    )

    # ---- Merge + normalize busy intervals to local tz ----
    merged_busy = planner.merge_busy_from_freebusy(calendars_busy)
    merged_busy = planner.normalize_intervals_tz(merged_busy, tz)

    print("\n=== DEBUG: Merged Busy Intervals (Local) ===")
    print(f"Busy blocks (merged): {len(merged_busy)}")
    for b in merged_busy:
        mins = int((b.end - b.start).total_seconds() // 60)
        print(f"- {b.start.isoformat()} → {b.end.isoformat()} ({mins} min)")

    # ---- Free slots ----
    free_slots = planner.invert_busy_to_free(work_start, work_end, merged_busy)

    print("\n=== DEBUG: Free Slots (Local) ===")
    print(f"Free slot count: {len(free_slots)}")
    if not free_slots:
        print("(No free slots found in the window.)")

    for slot in free_slots:
        mins = int((slot.end - slot.start).total_seconds() // 60)
        print(f"- {slot.start.isoformat()} → {slot.end.isoformat()} ({mins} min)")
        # ---- Propose goal blocks (baseline) ----
    # You can change these goals later, or load them from config/user input.
    goals = [
        ("Deep Work", 120),
        ("Admin", 30),
        ("Break/Lunch", 30),
    ]

    blocks = planner.propose_blocks(free_slots, goals)

    print("\n=== DEBUG: Proposed Goal Blocks ===")
    print(f"Proposed block count: {len(blocks)}")
    if not blocks:
        print("(No goal blocks could be allocated.)")

    for b in blocks:
        print(f"- {b['label']}: {b['start']} → {b['end']} ({b['minutes']} min)")



if __name__ == "__main__":
    main()
