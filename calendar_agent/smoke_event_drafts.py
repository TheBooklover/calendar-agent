# calendar_agent/smoke_event_drafts.py
"""
Generate DRAFT Google Calendar event payloads from proposed blocks.

Safety:
- DOES NOT write to Google Calendar.
- Prints JSON payloads you could later insert into the primary calendar.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_agent.google_auth import get_calendar_service
from calendar_agent.gcal_tools import list_calendars, freebusy_query
from calendar_agent import planner


def read_planning_calendar_ids() -> set[str]:
    """
    Parse PLANNING_CALENDAR_IDS from environment into a set.
    """
    raw = os.getenv("PLANNING_CALENDAR_IDS", "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def build_event_payload(label: str, start_rfc3339: str, end_rfc3339: str, tz_name: str) -> dict:
    """
    Convert a planned block into a Google Calendar event payload.
    """
    return {
        "summary": label,
        "start": {"dateTime": start_rfc3339, "timeZone": tz_name},
        "end": {"dateTime": end_rfc3339, "timeZone": tz_name},
        "description": "Auto-drafted by Calendar Agent (not created yet).",
    }


def main() -> None:
    tz_name = "America/Toronto"
    tz = ZoneInfo(tz_name)

    planning_ids = read_planning_calendar_ids()

    # Fixed date for smoke test
    target_date = datetime(2025, 12, 16, tzinfo=tz)
    window_start = target_date.replace(hour=4, minute=0, second=0, microsecond=0)
    window_end = target_date.replace(hour=22, minute=0, second=0, microsecond=0)

    service = get_calendar_service(["https://www.googleapis.com/auth/calendar"])

    calendars = list_calendars(service)
    all_ids = [c["id"] for c in calendars if c.get("id")]

    # Apply optional filter
    if planning_ids:
        calendar_ids = [cid for cid in all_ids if cid in planning_ids]
    else:
        calendar_ids = all_ids

    calendars_busy = freebusy_query(
        service=service,
        time_min=window_start.isoformat(),
        time_max=window_end.isoformat(),
        calendar_ids=calendar_ids,
    )

    merged_busy = planner.merge_busy_from_freebusy(calendars_busy)
    merged_busy = planner.normalize_intervals_tz(merged_busy, tz)

    free_slots = planner.invert_busy_to_free(window_start, window_end, merged_busy)

    # Same baseline goals as smoke_planner
    goals = [
        ("Deep Work", 120),
        ("Admin", 30),
        ("Break/Lunch", 30),
    ]
    blocks = planner.propose_blocks(free_slots, goals)

    drafts = [build_event_payload(b["label"], b["start"], b["end"], tz_name) for b in blocks]

    print("\n=== DRAFT EVENT PAYLOADS (NOT CREATED) ===\n")
    print(json.dumps(drafts, indent=2))


if __name__ == "__main__":
    main()
