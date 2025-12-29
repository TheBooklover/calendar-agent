# calendar_agent/google_auth.py
"""
Google Calendar OAuth helpers for a WEB service (Render).

This file supports two things:
1) API server OAuth flow: /auth/start and /auth/callback (web app flow)
2) Getting an authenticated Calendar service from token.json

IMPORTANT:
- client_id / client_secret / redirect_uri come from environment variables
- token.json is created after the callback exchange
"""

from __future__ import annotations

import os
from typing import List, Tuple, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
# Token persistence on Render Free: store token JSON in Redis (Upstash)
from calendar_agent.token_store import save_token
import json  # Needed to parse token JSON loaded from Redis

# Token persistence on Render Free: load token JSON from Redis (Upstash)
from calendar_agent.token_store import load_token



def build_google_flow(scopes: List[str]) -> Flow:
    """
    Build a Google OAuth Flow for a web server using env vars.

    Required env vars:
      - GOOGLE_CLIENT_ID
      - GOOGLE_CLIENT_SECRET
      - OAUTH_REDIRECT_URI  (e.g. https://calendar.mwchadwick.com/auth/callback)
    """
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.environ["OAUTH_REDIRECT_URI"]],
        }
    }

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=scopes,
        redirect_uri=os.environ["OAUTH_REDIRECT_URI"],
    )
    return flow


def save_credentials_to_token(creds: Credentials, token_path: str = "token.json") -> None:
    """
    Persist OAuth credentials externally (Redis/Upstash) so future requests can use them.

    NOTE:
    - token_path is kept only for backward compatibility with existing callers.
    - We do NOT write to disk because Render free instances have ephemeral filesystems.
    """
    # creds.to_json() returns a JSON string representing the credentials.
    save_token(creds.to_json())



def get_calendar_service(scopes: List[str], token_path: str = "token.json"):
    """
    Return a Google Calendar API client.

    On Render free, we cannot rely on token.json existing on disk.
    Instead, we load the stored token JSON from Redis (Upstash).

    NOTE:
    - token_path is kept for backward compatibility, but ignored for persistence.
    """
    creds: Optional[Credentials] = None

    # Load token JSON from Redis (Upstash) instead of checking the filesystem.
    token_json = load_token()
    if token_json:
        # Convert the stored JSON string into a dict for the Google library.
        token_info = json.loads(token_json)

        # Rehydrate credentials from stored token info.
        # This is the in-memory equivalent of from_authorized_user_file(...).
        creds = Credentials.from_authorized_user_info(token_info, scopes)

    if not creds:
        raise RuntimeError("No stored OAuth token. Run /auth/start to authenticate first.")

    # If creds are expired, refresh them and persist the refreshed version back to Redis.
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials_to_token(creds, token_path=token_path)
        else:
            raise RuntimeError("Stored OAuth token is invalid and cannot refresh. Run /auth/start again.")

    return build("calendar", "v3", credentials=creds)

