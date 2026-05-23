"""Quora answers adapter via Apify.

Quora actively fights scraping, so the adapter degrades gracefully on actor errors.
"""

from __future__ import annotations

import html
import re
from typing import Any

from scout.sources._apify import ApifyError, run_actor
from scout.sources.base import SourceSignal, summarize_items

DEFAULT_ACTOR = "epctex/quora-scraper"


def search(
    query: str,
    limit: int = 25,
    scope: list[str] | None = None,
    actor_id: str = DEFAULT_ACTOR,
    min_text_length: int = 100,
) -> SourceSignal:
    """Pull Quora answers matching the query.

    `scope` is a list of Quora topics (e.g. ["sales-operations", "b2b-saas"]).
    Quora's topic URLs follow https://www.quora.com/topic/<topic-slug>.
    """
    topics = scope or []
    payload = {
        "search": query,
        "topics": topics,
        "maxItems": limit,
        "includeAnswers": True,
    }
    try:
        raw = run_actor(actor_id, payload)
    except ApifyError as exc:
        return SourceSignal(
            source="quora",
            query=query,
            item_count=0,
            items=[{"error": str(exc)}],
            summary=f"Quora fetch failed: {exc}",
        )

    items: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        normalized = _normalize(r)
        # Skip stubs/short answers — Quora often returns truncated previews
        if len(normalized.get("text", "")) < min_text_length and "error" not in normalized:
            continue
        items.append(normalized)

    real = [i for i in items if "error" not in i]
    return SourceSignal(
        source="quora",
        query=query,
        item_count=len(real),
        items=items,
        summary=summarize_items(real, "quora"),
    )


def _normalize(r: dict[str, Any]) -> dict[str, Any]:
    text = _strip_html(r.get("answer") or r.get("answerText") or r.get("body") or "")
    title = r.get("question") or r.get("title") or ""
    return {
        "id": r.get("id") or r.get("answerId") or r.get("url", ""),
        "title": title,
        "text": text[:2000],
        "url": r.get("url") or r.get("answerUrl") or "",
        "score": r.get("upvotes") or r.get("votes") or 0,
        "date": r.get("date") or r.get("createdAt") or "",
        "author": r.get("author") or r.get("authorName") or "",
        "topic": r.get("topic") or r.get("topicName") or "",
    }


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()
