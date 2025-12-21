# calendar_agent/token_store.py
import os
import requests

# Upstash REST credentials are stored in env vars
_UPSTASH_URL = os.environ["UPSTASH_REDIS_REST_URL"].rstrip("/")
_UPSTASH_TOKEN = os.environ["UPSTASH_REDIS_REST_TOKEN"]
_TOKEN_KEY = os.getenv("OAUTH_TOKEN_KEY", "calendar_agent:token")

_HEADERS = {"Authorization": f"Bearer {_UPSTASH_TOKEN}"}


def save_token(token_json: str) -> None:
    """
    Save the OAuth token JSON string into Redis.
    This replaces writing token.json to disk.
    """
    resp = requests.post(
        f"{_UPSTASH_URL}/set/{_TOKEN_KEY}",
        headers=_HEADERS,
        data=token_json.encode("utf-8"),
        timeout=10,
    )
    resp.raise_for_status()


def load_token() -> str | None:
    """
    Load the OAuth token JSON string from Redis.
    Returns None if no token is stored yet.
    """
    resp = requests.get(
        f"{_UPSTASH_URL}/get/{_TOKEN_KEY}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    # Upstash returns something like {"result":"..."} or {"result":null}
    return data.get("result")
