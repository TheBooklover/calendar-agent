# calendar_agent/smoke_freebusy.py
"""
Smoke test: FreeBusy across all calendars on your calendar list.

This verifies:
- multi-calendar support
- freebusy.query endpoint works
- we can compute total busy blocks
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_agent.google_auth import get_calendar_service
from calendar_agent.gcal_tools import list_calendars, freebusy_query


def main() -> None:
    """
    Query busy blocks for today 09:00–17:00 (America/Toronto) across all calendars.
    """
    tz = ZoneInfo("America/Toronto")

    now = datetime.now(tz)
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=17, minute=0, second=0, microsecond=0)

    service = get_calendar_service(["https://www.googleapis.com/auth/calendar"])

    calendars = list_calendars(service)
    calendar_ids = [c["id"] for c in calendars if c.get("id")]

    calendars_busy = freebusy_query(
        service=service,
        time_min=start.isoformat(),
        time_max=end.isoformat(),
        calendar_ids=calendar_ids,
    )

    total_busy = sum(len(v.get("busy", [])) for v in calendars_busy.values())

    print(f"Work window: {start.isoformat()} → {end.isoformat()}")
    print(f"Calendars queried: {len(calendar_ids)}")
    print(f"Total busy blocks (across calendars): {total_busy}\n")

    # Print first 15 busy blocks across all calendars so we can confirm it looks real
    printed = 0
    for cal_id, data in calendars_busy.items():
        for b in data.get("busy", []):
            print(f"{cal_id}: {b['start']} → {b['end']}")
            printed += 1
            if printed >= 15:
                return


if __name__ == "__main__":
    main()
