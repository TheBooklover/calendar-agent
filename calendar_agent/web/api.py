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
# Load local environment variables from .env for local development
# (In Render, env vars are provided by the platform instead)
from dotenv import load_dotenv
load_dotenv()
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
print("LOADED API FILE:", __file__, flush=True)
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

def _env_truthy(name: str, default: str = "0") -> bool:
    """
    Interpret env vars like "1", "true", "yes", "on" as True.

    This is useful for demo mode toggles in hosted environments (Render, etc.).
    """
    raw = os.getenv(name, default).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _coerce_min_block_map(raw: dict[str, Any] | None) -> dict[str, int] | None:
    """
    Validate and coerce min_block_minutes_by_label into dict[str, int] with guardrails.

    Why guardrails matter:
    - Prevents nonsense inputs (negative minutes, huge values)
    - Keeps your API stable and safe for a public demo
    """
    if raw is None:
        return None

    out: dict[str, int] = {}

    for label, value in raw.items():
        if not isinstance(label, str):
            raise HTTPException(status_code=400, detail="min_block_minutes_by_label keys must be strings")

        try:
            minutes = int(value)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"min_block_minutes_by_label['{label}'] must be an integer",
            )

        # Guardrails: 5–240 minutes keeps this sane for a calendar agent demo
        if minutes < 5 or minutes > 240:
            raise HTTPException(
                status_code=400,
                detail=f"min_block_minutes_by_label['{label}'] must be between 5 and 240",
            )

        out[label] = minutes

    return out


def _resolve_planner_settings(req: "PreviewRequest") -> dict[str, Any]:
    """
    Resolve planner settings using a clear priority order:

    1) Explicit request fields win.
    2) If demo_mode=True (request) OR PLANNER_DEMO_MODE=1 (env),
       apply A1 defaults ONLY when min_block_minutes_by_label is not provided.

    A1 default used here:
      - Deep Work min block = 30
      - Admin min block = 30

    Note: buffer_minutes defaults to 10 if not provided.
    """
    buffer_minutes = req.buffer_minutes if req.buffer_minutes is not None else 10
    min_blocks = _coerce_min_block_map(req.min_block_minutes_by_label)

    demo_from_req = bool(req.demo_mode) if req.demo_mode is not None else False
    demo_from_env = _env_truthy("PLANNER_DEMO_MODE", "0")
    demo_on = demo_from_req or demo_from_env

    # Apply A1 defaults only if caller didn't explicitly provide min_blocks
    if demo_on and min_blocks is None:
        min_blocks = {"Deep Work": 30, "Admin": 30}

    return {
        "buffer_minutes": buffer_minutes,
        "min_block_minutes_by_label": min_blocks,
        "demo_mode_applied": demo_on,
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
    # -----------------------
    # V0.5 planner controls
    # -----------------------

    buffer_minutes: int | None = Field(
        None,
        ge=0,
        le=60,
        description="Minutes of buffer inserted BETWEEN scheduled blocks (V0.5 control)",
    )

    min_block_minutes_by_label: dict[str, int] | None = Field(
        None,
        description="Optional per-label minimum block sizes, e.g. {'Deep Work': 30, 'Admin': 30}",
    )

    demo_mode: bool | None = Field(
        None,
        description="If true, applies A1 demo defaults when overrides are not provided",
    )



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
    # Debug: log the redirect_uri used in the OAuth request
    print("OAUTH redirect_uri:", flow.redirect_uri)


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
    Exchanges the code for tokens and saves token.json (locally) or Upstash (in prod).
    """
    print("🔥 auth_callback hit", flush=True)

    scopes = ["https://www.googleapis.com/auth/calendar"]

    # Read "code" from query params
    code = request.query_params.get("code")
    if not code:
        # Helpful error if someone hits /auth/callback directly without completing consent
        raise HTTPException(status_code=400, detail="Missing ?code= in callback URL")

    # Rebuild the OAuth flow with the same redirect_uri and scopes
    flow = build_google_flow(scopes)

    # Exchange the authorization code for tokens
    flow.fetch_token(code=code)

    # Persist credentials so future API calls work without reauth
    creds = flow.credentials

    # IMPORTANT: use token_store abstraction
    # - local dev (no Upstash env vars): writes token.json to disk
    # - production (Upstash configured): writes token JSON to Redis
    from calendar_agent.token_store import save_token
    save_token(creds.to_json())

    # Helpful debug line so you can confirm this ran in uvicorn logs
    print("✅ Saved OAuth token via token_store", flush=True)

    return PlainTextResponse("✅ OAuth complete. You can close this tab and return to the app.")





@app.get("/health")
def health():
    """
    Health check endpoint.
    Used to confirm the service is running.
    """
    return {"ok": True}

@app.get("/demo/v05")
def demo_v05():
    """
    Deterministic, OAuth-free demo of the V0.5 planner.

    Why:
    - You can hit ONE endpoint and see the planner work instantly.
    - Does not depend on Google Calendar availability.
    - Mirrors the A1 acceptance scenario (packing with buffer between blocks).
    """
    tz = ZoneInfo("America/Toronto")

    # A1 demo slot: 80 minutes total
    free_slots = [
        planner.Interval(
            start=datetime(2025, 12, 29, 9, 0, tzinfo=tz),
            end=datetime(2025, 12, 29, 10, 40, tzinfo=tz),
        )
    ]

    goals = [
        ("Deep Work", 60),
        ("Admin", 30),
    ]

    # Force A1-style settings for a compelling default demo
    settings = {
        "buffer_minutes": 10,
        "min_block_minutes_by_label": {"Deep Work": 30, "Admin": 30},
        "demo_mode_applied": True,
    }

    blocks = planner.propose_blocks(
        free=free_slots,
        goals=goals,
        buffer_minutes=settings["buffer_minutes"],
        min_block_minutes_by_label=settings["min_block_minutes_by_label"],
    )

    return {
        "demo": "v0.5_offline",
        "tz": "America/Toronto",
        "window": {"start": free_slots[0].start.isoformat(), "end": free_slots[0].end.isoformat()},
        "planner_settings": settings,
        "free_slots": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "minutes": int((s.end - s.start).total_seconds() // 60),
            }
            for s in free_slots
        ],
        "proposed_blocks": blocks,
        "notes": [
            "This endpoint does not call Google Calendar.",
            "It exists to demonstrate deterministic V0.5 scheduling behavior reliably.",
            "It matches the A1 acceptance scenario: buffer is applied between blocks, enabling packing.",
        ],
    }



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
    print("DEBUG: /plan/preview hit", flush=True)  # TEMP: confirms endpoint is executing
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

    print(f"DEBUG: Busy intervals: {len(merged_busy)}", flush=True)
    for b in merged_busy:
        print({"start": b.start.isoformat(), "end": b.end.isoformat()}, flush=True)


    # Compute free slots inside the window
    free_slots = planner.invert_busy_to_free(window_start, window_end, merged_busy)

    # Build the simple goals list (Phase 2 will replace this with configurable block types)
    goals = [
        ("Deep Work", req.deep_work_minutes),
        ("Admin", req.admin_minutes),
        ("Break/Lunch", req.break_minutes),
    ]

    # Allocate blocks into free slots
    # Resolve V0.5 planner controls (buffer, min block sizes, demo defaults)
    settings = _resolve_planner_settings(req)

    # Allocate blocks into free slots using V0.5 planner controls
    blocks = planner.propose_blocks(
        free=free_slots,
        goals=goals,
        buffer_minutes=settings["buffer_minutes"],
        min_block_minutes_by_label=settings["min_block_minutes_by_label"],
    )

    # --- TEMP DEBUG (remove later) ---
    print("\n=== DEBUG: Proposed blocks from planner ===", flush=True)
    for b in blocks:
        print(b, flush=True)
# --- END TEMP DEBUG ---


    # Return UI-friendly JSON
    return {
        "date": req.date,
        "tz": req.tz,
        "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "planner_settings": settings,  # <-- V0.5: show applied controls
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

@app.post("/plan/preview_demo")
def plan_preview_demo(req: PreviewRequest):
    """
    Same as /plan/preview, but forces demo_mode=True.

    Purpose:
    - UI can call this endpoint to always use A1-friendly defaults
      without needing to pass planner knobs explicitly.
    """
    # Force demo behavior (A1 defaults) without requiring UI changes
    req.demo_mode = True

    # Reuse the normal preview logic
    return plan_preview(req)




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
