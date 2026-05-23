"""G2/Capterra review adapter via Apify. Targets negative reviews (1-3 stars)."""

from __future__ import annotations

from typing import Any

from scout.sources._apify import ApifyError, run_actor
from scout.sources.base import SourceSignal, summarize_items

DEFAULT_ACTOR = "epctex/g2-scraper"


def search(
    query: str,
    limit: int = 25,
    scope: list[str] | None = None,
    actor_id: str = DEFAULT_ACTOR,
    max_stars: int = 3,
) -> SourceSignal:
    """Pull 1-`max_stars` star reviews matching the query.

    `scope` is a list of software categories (e.g. ["sales-engagement"]). If given,
    the actor scopes the search to those category pages on G2.
    """
    categories = scope or []
    payload = {
        "search": query,
        "categories": categories,
        "maxReviews": limit,
        "maxStarRating": max_stars,
        "minStarRating": 1,
        "includeCons": True,
        "includeSwitchReason": True,
    }
    try:
        raw = run_actor(actor_id, payload)
    except ApifyError as exc:
        return SourceSignal(
            source="g2",
            query=query,
            item_count=0,
            items=[{"error": str(exc)}],
            summary=f"G2 fetch failed: {exc}",
        )

    items = [_normalize(r) for r in raw if isinstance(r, dict) and not _is_above_threshold(r, max_stars)]
    real = [i for i in items if "error" not in i]
    return SourceSignal(
        source="g2",
        query=query,
        item_count=len(real),
        items=items,
        summary=summarize_items(real, "g2"),
    )


def _is_above_threshold(r: dict[str, Any], max_stars: int) -> bool:
    """Filter out positive reviews defensively even if the actor didn't honor maxStarRating."""
    rating = r.get("rating") or r.get("stars") or r.get("starRating") or 0
    try:
        return float(rating) > max_stars
    except (TypeError, ValueError):
        return False


def _normalize(r: dict[str, Any]) -> dict[str, Any]:
    title = r.get("title") or r.get("headline") or ""
    cons = r.get("cons") or r.get("dislikes") or ""
    switch_reason = r.get("switchReason") or r.get("whyISwitched") or ""
    body_parts = [
        r.get("body") or r.get("review") or "",
        f"\n\nCons: {cons}" if cons else "",
        f"\n\nWhy I switched: {switch_reason}" if switch_reason else "",
    ]
    text = "".join(p for p in body_parts if p).strip()
    return {
        "id": r.get("id") or r.get("reviewId") or r.get("url", ""),
        "title": title,
        "text": text[:2000],
        "url": r.get("url") or r.get("link") or "",
        "score": r.get("rating") or r.get("stars") or 0,
        "date": r.get("date") or r.get("publishedAt") or "",
        "author": r.get("reviewer") or r.get("author") or "",
        "product": r.get("product") or r.get("software") or "",
        "category": r.get("category") or "",
    }
