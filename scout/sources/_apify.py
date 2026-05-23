"""Thin Apify wrapper. One function: run an actor synchronously and return its dataset items.

Uses the run-sync-get-dataset-items endpoint, which blocks until the run finishes
and returns items in one HTTP call — no polling needed.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_BASE = "https://api.apify.com/v2"
DEFAULT_TIMEOUT = 180  # seconds; Apify actors typically finish in 10-60s


class ApifyError(RuntimeError):
    """Raised when Apify call fails or token is missing."""


def _get_token() -> str:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise ApifyError(
            "Missing APIFY_TOKEN. Set it in .env (get one at https://console.apify.com/account/integrations)."
        )
    return token


def run_actor(
    actor_id: str,
    payload: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Run an Apify actor synchronously and return its dataset items.

    Args:
        actor_id: e.g. "trudax/reddit-scraper-lite"
        payload: input JSON for the actor
        timeout: HTTP timeout in seconds

    Returns:
        List of dataset items (dicts). Shape is actor-specific.

    Raises:
        ApifyError on HTTP failure or missing token.
    """
    token = _get_token()
    # Apify accepts either "user/actor" or "user~actor" in URLs; normalize to the slash form
    encoded_id = actor_id.replace("~", "/")
    url = f"{APIFY_BASE}/acts/{encoded_id.replace('/', '~')}/run-sync-get-dataset-items"
    params = {"token": token}
    try:
        resp = requests.post(url, params=params, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise ApifyError(f"Apify request failed for {actor_id}: {exc}") from exc
    if resp.status_code >= 400:
        raise ApifyError(
            f"Apify actor {actor_id} returned HTTP {resp.status_code}: {resp.text[:300]}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise ApifyError(f"Apify response from {actor_id} not JSON: {resp.text[:300]}") from exc
