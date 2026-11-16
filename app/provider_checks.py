"""Explicit, fixed-destination provider connectivity checks.

Never log or return credential material. This module intentionally supports
only the OpenAI API and does not follow redirects.
"""
from __future__ import annotations

import httpx

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


def check_openai_api_key(api_key: str) -> dict[str, str | bool]:
    if not api_key or len(api_key) > 8192:
        return {"status": "invalid_credential", "connected": False}

    try:
        response = httpx.get(
            OPENAI_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=8.0,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        return {"status": "timeout", "connected": False}
    except httpx.RequestError:
        return {"status": "provider_unreachable", "connected": False}

    if response.status_code == 200:
        return {"status": "connected", "connected": True}
    if response.status_code == 401:
        return {"status": "invalid_credential", "connected": False}
    if response.status_code == 403:
        return {"status": "insufficient_permissions", "connected": False}
    if response.status_code == 429:
        return {"status": "rate_limited", "connected": False}
    if 300 <= response.status_code < 400:
        return {"status": "unexpected_redirect", "connected": False}
    return {"status": "provider_error", "connected": False}
