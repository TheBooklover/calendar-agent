# calendar_agent/gcal_tools.py
"""
Deterministic Google Calendar tools.

These are "safe hands" for the agent:
- Read any calendars the user can access (multi-calendar support)
- Write ONLY to the primary calendar
- Never delete events
"""

from __future__ import annotations

from typing import Any, Dict, List


def list_calendars(service) -> List[Dict[str, Any]]:
    """
    List calendars available on the user's calendar list.
    Includes primary + subscribed + shared calendars.

    Returns:
        Simplified list: [{id, summary, accessRole, primary}, ...]
    """
    resp = service.calendarList().list().execute()
    items = resp.get("items", [])
    out: List[Dict[str, Any]] = []

    for cal in items:
        out.append(
            {
                "id": cal.get("id"),
                "summary": cal.get("summary"),
                "accessRole": cal.get("accessRole"),
                "primary": cal.get("primary", False),
            }
        )

    return out

def list_events_primary(
    service,
    time_min: str,
    time_max: str,
) -> List[Dict[str, Any]]:
    """
    List events on the PRIMARY calendar within a time window.

    Why this exists:
    - We need to detect events previously created by this app (idempotency)
    - We only read primary here to match our "safe hands" rule for writes/management

    Args:
        time_min/time_max: RFC3339 timestamps (inclusive-ish start, exclusive-ish end)

    Returns:
        A list of raw Google Calendar event objects.
    """
    events: List[Dict[str, Any]] = []
    page_token: str | None = None

    # Google Calendar API paginates results; we loop until done.
    while True:
        resp = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,       # Expand recurring events into individual instances
                orderBy="startTime",     # Makes results deterministic and easier to debug
                pageToken=page_token,
            )
            .execute()
        )

        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")

        if not page_token:
            break

    return events


def freebusy_query(
    service,
    time_min: str,
    time_max: str,
    calendar_ids: List[str],
) -> Dict[str, Any]:
    """
    Query busy blocks across multiple calendars.

    Args:
        time_min/time_max: RFC3339 timestamps
        calendar_ids: calendar IDs to query

    Returns:
        Dict keyed by calendarId with busy intervals, like:
        { "calendarId": { "busy": [{"start": "...", "end": "..."}, ...] }, ... }
    """
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": cid} for cid in calendar_ids],
    }
    resp = service.freebusy().query(body=body).execute()
    return resp.get("calendars", {})


def create_event_primary(service, event_payload: Dict[str, Any], confirm: bool) -> Dict[str, Any]:
    """
    Create an event on the PRIMARY calendar only.

    Safety:
    - If confirm is False, returns the draft and does not write.
    """
    if not confirm:
        return {"status": "needs_confirmation", "calendarId": "primary", "draft": event_payload}

    created = service.events().insert(calendarId="primary", body=event_payload).execute()
    return {"status": "created", "event": created}


def patch_event_primary(
    service,
    event_id: str,
    patch_fields: Dict[str, Any],
    confirm: bool,
) -> Dict[str, Any]:
    """
    Patch/update fields on an event on the PRIMARY calendar only.

    Safety:
    - If confirm is False, returns the patch draft and does not write.
    """
    if not confirm:
        return {
            "status": "needs_confirmation",
            "calendarId": "primary",
            "eventId": event_id,
            "patch": patch_fields,
        }

    updated = service.events().patch(calendarId="primary", eventId=event_id, body=patch_fields).execute()
    return {"status": "updated", "event": updated}
