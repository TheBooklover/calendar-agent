# calendar_agent/token_store.py
"""
Token storage abstraction.

Goal:
- Production (Render): no reliable disk -> store token JSON in Upstash (Redis REST)
- Local dev: store token JSON on disk as token.json (so you don't re-auth on every restart)

Why this matters:
- uvicorn --reload restarts the process often; memory-only token storage is painful locally.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests

# --- Local fallback path (disk) ---
# This is what Pt.4 Step 4.5 expects to exist after successful OAuth.
_LOCAL_TOKEN_PATH = Path("token.json")


def _upstash_config() -> tuple[Optional[str], Optional[str]]:
    """
    Read Upstash env vars safely.

    IMPORTANT:
    - Upstash is ONLY used when UPSTASH_ENABLED=1.
    - This prevents local dev from accidentally writing tokens to Redis.
    """
    # Local guardrail: require explicit opt-in
    if os.getenv("UPSTASH_ENABLED") != "1":
        return None, None

    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None, None
    return url.rstrip("/"), token



def save_token(token_json: str) -> None:
    """
    Persist token JSON.

    - If Upstash is configured: write to Redis
    - Else (local dev): write to token.json on disk
    """
    url, token = _upstash_config()

    # TEMP DEBUG: prove which branch we take + where we'd write the file
    from pathlib import Path
    import os
    print("DEBUG save_token(): cwd =", os.getcwd(), flush=True)
    print("DEBUG save_token(): upstash_configured =", bool(url and token), flush=True)
    print("DEBUG save_token(): token.json abs path =", str(Path('token.json').resolve()), flush=True)


    # Local dev: write token to disk
    if not url or not token:
        # Ensure we always write UTF-8 text, and create/overwrite the file
        _LOCAL_TOKEN_PATH.write_text(token_json, encoding="utf-8")
        return
    
    

    # Production: Upstash REST -> SET key value
    resp = requests.post(
        f"{url}/set/calendar_agent_token",
        headers={"Authorization": f"Bearer {token}"},
        data=token_json.encode("utf-8"),
        timeout=10,
    )
    resp.raise_for_status()


def load_token() -> Optional[str]:
    """
    Load token JSON.

    - If Upstash is configured: read from Redis
    - Else (local dev): read from token.json on disk if present
    """
    url, token = _upstash_config()

    # Local dev: read token from disk
    if not url or not token:
        if _LOCAL_TOKEN_PATH.exists():
            return _LOCAL_TOKEN_PATH.read_text(encoding="utf-8")
        return None

    # Production: Upstash REST -> GET key
    resp = requests.get(
        f"{url}/get/calendar_agent_token",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()

    data = resp.json()
    # Upstash returns {"result": "<value>"} when present, {"result": None} when missing.
    return data.get("result")
