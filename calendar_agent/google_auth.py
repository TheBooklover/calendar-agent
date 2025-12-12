# calendar_agent/google_auth.py
"""
Google Calendar authentication helper.

- Uses OAuth "Installed App" flow (desktop app) as in Google's Calendar API quickstart.
- Stores the user token in token.json (project root) after the first login.
- Returns an authenticated Google Calendar API service client.
"""

from __future__ import annotations

import os
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def get_calendar_service(
    scopes: List[str],
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
):
    """
    Build and return a Google Calendar API client.

    Args:
        scopes: OAuth scopes to request.
        credentials_path: Path to OAuth client secrets JSON downloaded from GCP.
        token_path: Path where the user's OAuth token is stored.

    Returns:
        Google Calendar API service client (calendar v3).
    """
    creds = None

    # Load existing token if present
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh token without prompting the user again
            creds.refresh(Request())
        else:
            # Launches a local server and opens a browser window for user consent
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        # Save the credentials for next run
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    # Build the Calendar API client
    service = build("calendar", "v3", credentials=creds)
    return service
