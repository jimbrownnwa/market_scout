"""Reddit search adapter via Apify (replaces PRAW)."""

from __future__ import annotations

from typing import Any

from scout.sources._apify import ApifyError, run_actor
from scout.sources.base import SourceSignal, summarize_items

DEFAULT_ACTOR = "trudax/reddit-scraper-lite"


def search(
    query: str,
    limit: int = 25,
    scope: list[str] | None = None,
    actor_id: str = DEFAULT_ACTOR,
    sort: str = "top",
    time_filter: str = "year",
) -> SourceSignal:
    """Search Reddit for query-matching posts. `scope` is a list of subreddit names."""
    subreddits = scope or []
    start_urls = _build_start_urls(query, subreddits, sort, time_filter)
    payload = {
        "startUrls": start_urls,
        "maxItems": limit * max(1, len(start_urls) or 1),
        "maxPostCount": limit,
        "searches": [query] if query else [],
        "type": "posts",
        "sort": sort,
        "time": time_filter,
    }
    try:
        raw = run_actor(actor_id, payload)
    except ApifyError as exc:
        items = [{"error": str(exc)}]
        return SourceSignal(
            source="reddit",
            query=query,
            item_count=0,
            items=items,
            summary=f"Reddit fetch failed: {exc}",
        )

    items = [_normalize(r) for r in raw if isinstance(r, dict)]
    real = [i for i in items if "error" not in i]
    return SourceSignal(
        source="reddit",
        query=query,
        item_count=len(real),
        items=items,
        summary=summarize_items(real, "reddit"),
    )


def _build_start_urls(query: str, subreddits: list[str], sort: str, time_filter: str) -> list[dict[str, str]]:
    if not subreddits:
        # global search
        return [{"url": f"https://www.reddit.com/search/?q={query.replace(' ', '+')}&sort={sort}&t={time_filter}"}]
    urls: list[dict[str, str]] = []
    for sub in subreddits:
        sub = sub.strip()
        if sub.startswith("r/"):
            sub = sub[2:]
        sub = sub.strip("/")
        if not sub:
            continue
        if query:
            urls.append({
                "url": f"https://www.reddit.com/r/{sub}/search/?q={query.replace(' ', '+')}&restrict_sr=1&sort={sort}&t={time_filter}"
            })
        else:
            urls.append({"url": f"https://www.reddit.com/r/{sub}/{sort}/?t={time_filter}"})
    return urls


def _normalize(r: dict[str, Any]) -> dict[str, Any]:
    """Map an Apify Reddit result to our unified item shape."""
    return {
        "id": r.get("id") or r.get("postId") or r.get("url", ""),
        "title": r.get("title") or "",
        "text": (r.get("body") or r.get("selftext") or r.get("text") or "")[:2000],
        "url": r.get("url") or r.get("permalink") or "",
        "score": r.get("upVotes") or r.get("score") or r.get("ups") or 0,
        "date": r.get("createdAt") or r.get("created") or "",
        "author": r.get("username") or r.get("author") or "",
        "subreddit": r.get("communityName") or r.get("subreddit") or "",
        "num_comments": r.get("numberOfComments") or r.get("num_comments") or 0,
    }
