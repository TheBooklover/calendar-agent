# calendar_agent/smoke_tools.py
"""
Smoke test for the project's tool layer (no OpenAI involved).

Goal:
- Use our google_auth.py to get a service
- Use gcal_tools.py to list calendars
"""

from __future__ import annotations

from calendar_agent.google_auth import get_calendar_service
from calendar_agent.gcal_tools import list_calendars


def main() -> None:
    """
    Authenticate (using token.json if present) and list calendars.
    """
    scopes = ["https://www.googleapis.com/auth/calendar"]
    service = get_calendar_service(scopes=scopes)

    calendars = list_calendars(service)
    print(f"Calendars found: {len(calendars)}\n")
    for c in calendars:
        print(f"- {c['summary']} | primary={c['primary']} | accessRole={c['accessRole']} | id={c['id']}")


if __name__ == "__main__":
    main()
