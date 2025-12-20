"""
FastAPI wrapper around the calendar agent.

This exposes a minimal HTTP API so a frontend can:
- list calendars (read)
- preview a plan (read-only: free slots + proposed blocks)
- create events on primary (write, behind explicit confirm)
- create ONLY selected blocks on primary (write, behind explicit confirm)

Why this exists:
- Your agent logic (planner + gcal tools) is the "engine"
- This file is the "web wrapper" that lets a UI control the engine safely
"""

import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, PlainTextResponse
# Enables browser clients (like Replit) to call your API across origins
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from calendar_agent.google_auth import get_calendar_service, build_google_flow, save_credentials_to_token
from calendar_agent.gcal_tools import list_calendars, freebusy_query, create_event_primary
from calendar_agent import planner

# Create the FastAPI app object (the web server routes requests to functions below)
app = FastAPI(title="Calendar Agent API", version="0.2.0")
# --- CORS (development only) ---
# Allows your Replit-hosted frontend (different domain) to call this API.
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Dev-only. In production, restrict to your UI domain.
    allow_credentials=False,      # Must be False when allow_origins is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# Helpers (internal plumbing)
# ----------------------------

def _read_planning_calendar_ids() -> set[str]:
    """
    Read PLANNING_CALENDAR_IDS from env.

    If empty:
      - We interpret it as "include all calendars"
    If not empty:
      - We only query busy times from the specified calendars
    """
    raw = os.getenv("PLANNING_CALENDAR_IDS", "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _get_service():
    """
    Create an authenticated Google Calendar service client.

    If the server has not been authorized yet, this raises an error telling you
    to visit /auth/start.
    """
    try:
        return get_calendar_service(["https://www.googleapis.com/auth/calendar"])
    except RuntimeError as e:
        # Convert to a clean 401 so the frontend can handle it
        raise HTTPException(status_code=401, detail=str(e))



def _build_event_payload(label: str, start_rfc3339: str, end_rfc3339: str, tz_name: str) -> dict[str, Any]:
    """
    Convert a planned/selected block into a Google Calendar event payload.
    """
    return {
        "summary": label,
        "start": {"dateTime": start_rfc3339, "timeZone": tz_name},
        "end": {"dateTime": end_rfc3339, "timeZone": tz_name},
        "description": "Created by Calendar Agent (primary calendar only).",
    }


# ----------------------------
# Request models (API contracts)
# ----------------------------

class PreviewRequest(BaseModel):
    """
    Inputs controlled by the UI.
    """
    date: str = Field(..., description="Target date in YYYY-MM-DD")
    tz: str = Field("America/Toronto", description="IANA timezone string (e.g., America/Toronto)")
    window_start_hour: int = Field(4, ge=0, le=23, description="Start hour (0-23)")
    window_end_hour: int = Field(22, ge=0, le=23, description="End hour (0-23)")

    deep_work_minutes: int = Field(120, ge=0, le=600, description="Target minutes for Deep Work")
    admin_minutes: int = Field(30, ge=0, le=600, description="Target minutes for Admin")
    break_minutes: int = Field(30, ge=0, le=600, description="Target minutes for Break/Lunch")


class CreateRequest(BaseModel):
    """
    Create events from a preview configuration.

    NOTE: This creates ALL blocks returned by preview.
    We keep it for completeness and backward compatibility.
    """
    preview: PreviewRequest
    confirm: bool = False


class SelectedBlock(BaseModel):
    """
    Represents one block the user selected in the UI.

    - label: used as the Google Calendar event summary
    - start/end: RFC3339 timestamps (the format Google Calendar accepts)
    - minutes: optional; used for display/debug only (not required to create events)
    """
    label: str = Field(..., description="Block label, used as event summary")
    start: str = Field(..., description="RFC3339 start timestamp (e.g., 2025-12-15T08:45:00-05:00)")
    end: str = Field(..., description="RFC3339 end timestamp (e.g., 2025-12-15T10:20:00-05:00)")
    minutes: int | None = Field(None, description="Optional minutes (UI/debug)")


class CreateSelectedRequest(BaseModel):
    """
    Create ONLY the blocks selected (checked) by the user in the UI.

    This is the endpoint your Replit UI should call.
    """
    selected_blocks: list[SelectedBlock] = Field(..., description="Blocks to create on primary calendar")
    tz: str = Field("America/Toronto", description="IANA timezone string")
    confirm: bool = False


# ----------------------------
# Endpoints
# ----------------------------
# ----------------------------
# OAuth endpoints (Web Flow)
# ----------------------------

@app.get("/auth/start")
def auth_start():
    """
    Starts Google OAuth by redirecting the user to Google's consent screen.

    After the user consents, Google redirects back to OAUTH_REDIRECT_URI,
    which should be https://calendar.mwchadwick.com/auth/callback.
    """
    scopes = ["https://www.googleapis.com/auth/calendar"]

    # Build OAuth flow from env vars (GOOGLE_CLIENT_ID/SECRET, OAUTH_REDIRECT_URI)
    flow = build_google_flow(scopes)

    # Generate the Google consent URL
    auth_url, state = flow.authorization_url(
        access_type="offline",      # Requests refresh token
        prompt="consent",           # Helps ensure refresh token is issued
        include_granted_scopes="true",
    )

    # For a single-user demo, we do NOT persist state.
    # In a multi-user app, you MUST store and verify state to prevent CSRF.
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
def auth_callback(request: Request):
    """
    Handles Google's redirect back to us with a 'code' query param.
    Exchanges the code for tokens and saves token.json.
    """
    scopes = ["https://www.googleapis.com/auth/calendar"]

    # Read "code" from query params
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing ?code= in callback URL")

    # Rebuild the flow with the same redirect_uri and scopes
    flow = build_google_flow(scopes)

    # Exchange the authorization code for tokens
    flow.fetch_token(code=code)

    # Save credentials to token.json so future API calls work without reauth
    creds = flow.credentials
    save_credentials_to_token(creds)

    return PlainTextResponse("✅ OAuth complete. You can close this tab and return to the app.")




@app.get("/health")
def health():
    """
    Health check endpoint.
    Used to confirm the service is running.
    """
    return {"ok": True}


@app.get("/calendars")
def calendars():
    """
    Read-only: list calendars available to the OAuth user.
    Returns only what a UI needs (id + summary).
    """
    service = _get_service()
    cals = list_calendars(service)
    return [{"id": c.get("id"), "summary": c.get("summary")} for c in cals]


@app.post("/plan/preview")
def plan_preview(req: PreviewRequest):
    """
    Read-only: compute free slots and proposed blocks.

    Steps:
    1) Build the work window from date + hours in the requested timezone
    2) Ask Google Calendar for busy intervals (freebusy) across selected calendars
    3) Merge busy intervals, normalize to the timezone, invert to free slots
    4) Run your planner to allocate blocks across free slots
    5) Return JSON the UI can render
    """
    tz = ZoneInfo(req.tz)

    # Parse the date safely (expects YYYY-MM-DD)
    try:
        y, m, d = [int(x) for x in req.date.split("-")]
        target = datetime(y, m, d, tzinfo=tz)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {req.date}") from e

    # Build the time window for planning
    window_start = target.replace(hour=req.window_start_hour, minute=0, second=0, microsecond=0)
    window_end = target.replace(hour=req.window_end_hour, minute=0, second=0, microsecond=0)

    # Validate window
    if window_end <= window_start:
        raise HTTPException(status_code=400, detail="window_end_hour must be after window_start_hour")

    service = _get_service()

    # Determine which calendars to use when calculating "busy" time
    planning_ids = _read_planning_calendar_ids()
    cals = list_calendars(service)
    all_ids = [c["id"] for c in cals if c.get("id")]
    calendar_ids = [cid for cid in all_ids if cid in planning_ids] if planning_ids else all_ids

    # Query busy intervals from Google
    calendars_busy = freebusy_query(
        service=service,
        time_min=window_start.isoformat(),
        time_max=window_end.isoformat(),
        calendar_ids=calendar_ids,
    )

    # Merge + normalize intervals to ensure timezone correctness
    merged_busy = planner.merge_busy_from_freebusy(calendars_busy)
    merged_busy = planner.normalize_intervals_tz(merged_busy, tz)

    # Compute free slots inside the window
    free_slots = planner.invert_busy_to_free(window_start, window_end, merged_busy)

    # Build the simple goals list (Phase 2 will replace this with configurable block types)
    goals = [
        ("Deep Work", req.deep_work_minutes),
        ("Admin", req.admin_minutes),
        ("Break/Lunch", req.break_minutes),
    ]

    # Allocate blocks into free slots
    blocks = planner.propose_blocks(free_slots, goals)

    # Return UI-friendly JSON
    return {
        "date": req.date,
        "tz": req.tz,
        "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "free_slots": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "minutes": int((s.end - s.start).total_seconds() // 60),
            }
            for s in free_slots
        ],
        "proposed_blocks": blocks,
    }


@app.post("/plan/create")
def plan_create(req: CreateRequest):
    """
    Write: create events on PRIMARY calendar for ALL proposed blocks from preview.

    Safety:
    - Requires confirm=True (hard guardrail)

    Note:
    - This endpoint creates all proposed blocks. If you need selective creation,
      use /plan/create_selected.
    """
    if not req.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true to create events")

    preview_result = plan_preview(req.preview)
    service = _get_service()

    created = []
    for b in preview_result["proposed_blocks"]:
        payload = _build_event_payload(b["label"], b["start"], b["end"], req.preview.tz)
        result = create_event_primary(service=service, event_payload=payload, confirm=True)
        event = result.get("event", {})
        created.append({"id": event.get("id"), "summary": event.get("summary")})

    return {"created_count": len(created), "created": created}


@app.post("/plan/create_selected")
def plan_create_selected(req: CreateSelectedRequest):
    """
    Write: create events ONLY for blocks selected in the UI.
    Creates events on PRIMARY calendar only.

    Safety:
    - Requires confirm=True to proceed
    - If selected_blocks is empty, no writes occur
    """
    # Safety gate: never write unless caller explicitly confirms
    if not req.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true to create selected events")

    # No-op safely if nothing selected
    if not req.selected_blocks:
        return {"created_count": 0, "created": []}

    service = _get_service()
    created = []

    for b in req.selected_blocks:
        payload = _build_event_payload(
            label=b.label,
            start_rfc3339=b.start,
            end_rfc3339=b.end,
            tz_name=req.tz,
        )
        result = create_event_primary(service=service, event_payload=payload, confirm=True)
        event = result.get("event", {})
        created.append({"id": event.get("id"), "summary": event.get("summary")})

    return {"created_count": len(created), "created": created}
