# smoke_oauth.py
"""
OAuth smoke test for Google Calendar.

Purpose:
- Force Google OAuth browser flow
- Generate token.json
- Prove Calendar API access works
"""

from calendar_agent.google_auth import get_calendar_service


def main():
    scopes = ["https://www.googleapis.com/auth/calendar"]

    print("Starting OAuth flow...")
    service = get_calendar_service(scopes=scopes)

    print("Fetching calendars...")
    resp = service.calendarList().list().execute()
    calendars = resp.get("items", [])

    print(f"\nFound {len(calendars)} calendars:\n")
    for cal in calendars:
        print(
            f"- {cal.get('summary')} | "
            f"id={cal.get('id')} | "
            f"accessRole={cal.get('accessRole')} | "
            f"primary={cal.get('primary', False)}"
        )


if __name__ == "__main__":
    main()
