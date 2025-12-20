from __future__ import annotations

import os
from typing import List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def get_calendar_service(scopes: List[str]):
    """
    Google Calendar OAuth for a WEB APPLICATION (Render-compatible)
    """

    token_path = "token.json"

    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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

            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent",
            )

            # This should never be called directly in API mode
            raise RuntimeError(
                f"OAuth flow not completed. Visit this URL in a browser:\n{auth_url}"
            )

    return build("calendar", "v3", credentials=creds)
