"""Create Google Calendar events on the PRIMARY calendar from proposed blocks.

SAFETY DESIGN
-------------
- By default, this script DOES NOT write anything.
- To actually create events, you must explicitly set:
      CONFIRM_CREATE="true"
  in your environment.

This is your "write-capability" smoke test.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_agent.google_auth import get_calendar_service
from calendar_agent.gcal_tools import (
    list_calendars,
    freebusy_query,
    create_event_primary,
)
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
        "start": {
            "dateTime": start_rfc3339,
            "timeZone": tz_name,
        },
        "end": {
            "dateTime": end_rfc3339,
            "timeZone": tz_name,
        },
        "description": "Created by Calendar Agent (primary calendar only).",
    }


def main() -> None:
    tz_name = "America/Toronto"
    tz = ZoneInfo(tz_name)

    # Safety gate
    confirm_create = os.getenv("CONFIRM_CREATE", "").strip().lower() == "true"

    planning_ids = read_planning_calendar_ids()

    # Fixed date for smoke test
    target_date = datetime(2025, 12, 15, tzinfo=tz)
    window_start = target_date.replace(hour=4, minute=0, second=0, microsecond=0)
    window_end = target_date.replace(hour=22, minute=0, second=0, microsecond=0)

    service = get_calendar_service(["https://www.googleapis.com/auth/calendar"])

    calendars = list_calendars(service)
    all_ids = [c["id"] for c in calendars if c.get("id")]

    # Apply optional planning filter
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

    goals = [
        ("Deep Work", 120),
        ("Admin", 30),
        ("Break/Lunch", 30),
    ]

    blocks = planner.propose_blocks(free_slots, goals)

    drafts = [
        build_event_payload(b["label"], b["start"], b["end"], tz_name)
        for b in blocks
    ]

    print("\n=== PREVIEW: Events to Create on PRIMARY ===")
    if not drafts:
        print("No events to create.")
        return

    for d in drafts:
        print(
            f"- {d['summary']}: "
            f"{d['start']['dateTime']} → {d['end']['dateTime']} "
            f"({d['start']['timeZone']})"
        )

    if not confirm_create:
        print("\n=== SAFETY GATE ===")
        print('No events were created. To create them, set CONFIRM_CREATE="true" and re-run.')
        return

    print("\n=== CREATING EVENTS (PRIMARY) ===")

    created_count = 0
    for d in drafts:
        result = create_event_primary(
            service=service,
            event_payload=d,
            confirm=True,
        )
        event = result.get("event", {})
        created_count += 1
        print(f"Created: {event.get('summary')} | id={event.get('id')}")

    print(f"\nDone. Created {created_count} events on PRIMARY.")


if __name__ == "__main__":
    main()
