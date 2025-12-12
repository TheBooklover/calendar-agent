"""Smoke test: planning logic on top of FreeBusy (WITH DEBUG OUTPUT).

This script:
1) Queries busy blocks across all calendars
2) Prints per-calendar busy counts (with calendar names)
3) Merges busy blocks into one consolidated timeline
4) Inverts busy into free slots within work hours
5) Allocates goal blocks into free time

Run:
    python -u -m calendar_agent.smoke_planner
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_agent.google_auth import get_calendar_service
from calendar_agent.gcal_tools import list_calendars, freebusy_query
from calendar_agent import planner


def main() -> None:
    # ---- Config (hard-coded for smoke test) ----
    tz = ZoneInfo("America/Toronto")

    now = datetime.now(tz)
    work_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    work_end = now.replace(hour=17, minute=0, second=0, microsecond=0)

    # ---- Auth + service ----
    service = get_calendar_service(["https://www.googleapis.com/auth/calendar"])

    # ---- Calendars ----
    calendars = list_calendars(service)
    calendar_ids = [c["id"] for c in calendars if c.get("id")]

    # Map IDs to human-readable names for debugging
    id_to_name = {c["id"]: c["summary"] for c in calendars}

    print("\n=== DEBUG: Calendar Inventory ===")
    print(f"Total calendars on calendar list: {len(calendars)}")
    print("Calendars queried (id → name):")
    for cid in calendar_ids:
        print(f"- {cid} → {id_to_name.get(cid, '(unknown)')}")

    # ---- FreeBusy ----
    calendars_busy = freebusy_query(
        service=service,
        time_min=work_start.isoformat(),
        time_max=work_end.isoformat(),
        calendar_ids=calendar_ids,
    )

    print("\n=== DEBUG: Work Window ===")
    print(f"Work window: {work_start.isoformat()} → {work_end.isoformat()}")

    print("\n=== DEBUG: Busy Counts by Calendar (non-zero only) ===")
    any_busy = False
    for cal_id, data in calendars_busy.items():
        busy_list = data.get("busy", [])
        if busy_list:
            any_busy = True
            name = id_to_name.get(cal_id, cal_id)
            print(f"- {name} ({cal_id}): {len(busy_list)} busy blocks")
    if not any_busy:
        print("(No busy blocks returned for any calendar in this window.)")

    # ---- Merge busy blocks across calendars ----
    merged_busy = planner.merge_busy_from_freebusy(calendars_busy)

    print("\n=== DEBUG: Merged Busy Intervals ===")
    print(f"Busy blocks (merged): {len(merged_busy)}")
    if merged_busy:
        for b in merged_busy:
            mins = int((b.end - b.start).total_seconds() // 60)
            print(f"- {b.start.isoformat()} → {b.end.isoformat()} ({mins} min)")
    else:
        print("(No merged busy intervals.)")

    # ---- Compute free slots ----
    free_slots = planner.invert_busy_to_free(work_start, work_end, merged_busy)

    print("\n=== DEBUG: Free Slots ===")
    print(f"Free slot count: {len(free_slots)}")
    if free_slots:
        for slot in free_slots:
            mins = int((slot.end - slot.start).total_seconds() // 60)
            print(f"- {slot.start.isoformat()} → {slot.end.isoformat()} ({mins} min)")
    else:
        print("(No free slots found in the work window.)")

    # ---- Propose goal blocks ----
    goals = [("Deep Work", 120), ("Admin", 30), ("Break/Lunch", 30)]
    blocks = planner.propose_blocks(free_slots, goals)

    print("\n=== DEBUG: Proposed Goal Blocks ===")
    print(f"Proposed block count: {len(blocks)}")
    if blocks:
        for b in blocks:
            print(f"- {b['label']}: {b['start']} → {b['end']} ({b['minutes']} min)")
    else:
        print("(No goal blocks could be allocated.)")


if __name__ == "__main__":
    main()
