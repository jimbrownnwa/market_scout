"""Hacker News search adapter via the Algolia HN Search API.

No auth required. Pulls Ask HN threads and high-comment stories matching the query.
Optionally fetches top comments for the highest-engagement stories.

API docs: https://hn.algolia.com/api
"""

from __future__ import annotations

import html
import re
from typing import Any

import requests

from scout.sources.base import SourceSignal, summarize_items

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
DEFAULT_TIMEOUT = 30


def search(
    query: str,
    limit: int = 25,
    scope: list[str] | None = None,
    include_comments: bool = True,
    min_comments: int = 5,
) -> SourceSignal:
    """Search HN for stories + Ask HN threads matching the query.

    `scope` is ignored — HN has no subreddit equivalent. Kept for interface uniformity.
    """
    items: list[dict[str, Any]] = []

    for tag in ("ask_hn", "story"):
        try:
            params = {
                "query": query,
                "tags": tag,
                "hitsPerPage": limit,
                "numericFilters": f"num_comments>={min_comments}" if tag == "story" else None,
            }
            params = {k: v for k, v in params.items() if v is not None}
            resp = requests.get(f"{ALGOLIA_BASE}/search", params=params, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            for hit in data.get("hits", []):
                items.append(_normalize_hit(hit))
        except requests.RequestException as exc:
            items.append({"error": f"HN {tag} search failed: {exc}"})
            continue

    # Sort by score+comments and trim
    items.sort(key=lambda x: (x.get("score", 0) + x.get("num_comments", 0)), reverse=True)
    items = items[: limit * 2]

    if include_comments:
        items.extend(_fetch_top_comments(items[:5], query))

    real = [i for i in items if "error" not in i]
    return SourceSignal(
        source="hackernews",
        query=query,
        item_count=len(real),
        items=items,
        summary=summarize_items(real, "hackernews"),
    )


def _normalize_hit(hit: dict[str, Any]) -> dict[str, Any]:
    text = _strip_html(hit.get("story_text") or hit.get("comment_text") or "")
    object_id = hit.get("objectID") or ""
    return {
        "id": object_id,
        "title": hit.get("title") or "",
        "text": text[:2000],
        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
        "score": hit.get("points") or 0,
        "date": hit.get("created_at") or "",
        "author": hit.get("author") or "",
        "num_comments": hit.get("num_comments") or 0,
    }


def _fetch_top_comments(stories: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Pull top comments (text only) for the highest-engagement stories."""
    out: list[dict[str, Any]] = []
    for story in stories:
        story_id = story.get("id")
        if not story_id or "error" in story:
            continue
        try:
            resp = requests.get(
                f"{ALGOLIA_BASE}/search",
                params={"tags": f"comment,story_{story_id}", "hitsPerPage": 10},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            for hit in resp.json().get("hits", []):
                text = _strip_html(hit.get("comment_text") or "")
                if len(text) < 50:
                    continue
                out.append({
                    "id": hit.get("objectID") or "",
                    "title": "",
                    "text": text[:2000],
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "score": 0,
                    "date": hit.get("created_at") or "",
                    "author": hit.get("author") or "",
                    "parent_story": story_id,
                })
        except requests.RequestException:
            continue
    return out


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()
