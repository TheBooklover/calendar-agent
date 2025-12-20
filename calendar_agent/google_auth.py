# calendar_agent/google_auth.py
"""
Google Calendar authentication helper (server-friendly / web OAuth).

This module is designed to work in two environments:
1) Always-on servers (Render): user authorizes via /auth/start -> /auth/callback.
2) Local dev: same behavior (still uses web flow; no local_server browser popup).

Token storage:
- Writes token to token.json by default (good enough for a single-user demo).
- For multi-user or production-grade, you'd store tokens per user (DB/Redis).
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


DEFAULT_TOKEN_PATH = "token.json"


def _env(name: str) -> str:
    """Read a required environment variable or raise a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_google_flow(scopes: List[str]) -> Flow:
    """
    Build an OAuth Flow using a *Web application* OAuth client (client id/secret).
    Values come from environment variables set locally and on Render.

    Required env vars:
    - GOOGLE_CLIENT_ID
    - GOOGLE_CLIENT_SECRET
    - OAUTH_REDIRECT_URI  (e.g., https://calendar.mwchadwick.com/auth/callback)
    """
    client_id = _env("GOOGLE_CLIENT_ID")
    client_secret = _env("GOOGLE_CLIENT_SECRET")
    redirect_uri = _env("OAUTH_REDIRECT_URI")

    # Build "client_config" in the exact structure google-auth-oauthlib expects.
    # This avoids needing credentials.json on the server.
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = redirect_uri
    return flow


def load_credentials_from_token(scopes: List[str], token_path: str = DEFAULT_TOKEN_PATH) -> Optional[Credentials]:
    """
    Load credentials from token.json if it exists.

    Returns:
        Credentials if token exists, else None.
    """
    if os.path.exists(token_path):
        return Credentials.from_authorized_user_file(token_path, scopes)
    return None


def save_credentials_to_token(creds: Credentials, token_path: str = DEFAULT_TOKEN_PATH) -> None:
    """Persist credentials to token.json."""
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def get_calendar_service(scopes: List[str], token_path: str = DEFAULT_TOKEN_PATH):
    """
    Build and return a Google Calendar API client.

    Behavior:
    - If token exists and valid -> use it
    - If token expired and has refresh_token -> refresh silently
    - Else -> raise a clear error that auth is required

    This is server-safe: it does NOT try to open a browser window.
    """
    creds = load_credentials_from_token(scopes, token_path=token_path)

    if creds and creds.valid:
        return build("calendar", "v3", credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        # Refresh without prompting the user again
        creds.refresh(Request())
        save_credentials_to_token(creds, token_path=token_path)
        return build("calendar", "v3", credentials=creds)

    # No valid token and cannot refresh -> require web authorization
    raise RuntimeError("Google OAuth not authorized. Visit /auth/start to authorize this server.")
