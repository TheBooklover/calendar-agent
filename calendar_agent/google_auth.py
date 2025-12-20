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
    Save OAuth credentials to token.json so future requests can use them.
    """
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def get_calendar_service(scopes: List[str], token_path: str = "token.json"):
    """
    Load token.json and return a Google Calendar API client.

    If token.json is missing or invalid, you must run the OAuth flow
    via /auth/start and /auth/callback to generate a fresh token.
    """
    creds: Optional[Credentials] = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds:
        raise RuntimeError("token.json not found. Run /auth/start to authenticate first.")

    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials_to_token(creds, token_path=token_path)
        else:
            raise RuntimeError("token.json invalid and cannot refresh. Run /auth/start again.")

    return build("calendar", "v3", credentials=creds)
