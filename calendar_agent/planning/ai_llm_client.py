"""
LLM client wrapper (V0.7)

Design goals:
- Keep all network/model calls isolated here.
- Return raw text (JSON string) for parsing elsewhere.
- Do not embed business logic here (validation happens outside).

Implementation notes:
- Uses OpenAI API if OPENAI_API_KEY is set.
- If key is missing, raises a clear RuntimeError.
"""

from __future__ import annotations

import os
from typing import Optional


def get_openai_api_key() -> str:
    """
    Read OpenAI key from env.

    Why:
    - Avoid hardcoding secrets
    - Keep deployment simple (env vars)
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment")
    return key


def call_llm_json_only(prompt: str, *, model: str = "gpt-4.1-mini") -> str:
    """
    Call an LLM and request JSON-only output.

    Returns:
        Raw response text (expected to be JSON)

    Raises:
        RuntimeError if OPENAI_API_KEY is missing
        ImportError if openai package is not installed
    """
    _ = get_openai_api_key()

    # Import inside function so tests can import module without having openai installed
    from openai import OpenAI  # type: ignore

    client = OpenAI()

    # We enforce JSON-only output by instruction.
    # (Exact parameter names can vary by SDK version; keep this small and replaceable.)
    resp = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a planning assistant. "
                    "You must output ONLY valid JSON. No markdown, no extra text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    # The OpenAI Responses API returns a structured object; extract text.
    # If SDK differs, adjust this extraction—keep it localized here.
    return resp.output_text
