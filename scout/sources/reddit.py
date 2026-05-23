"""Reddit search adapter via PRAW. Reads credentials from env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any

import praw
from dotenv import load_dotenv

load_dotenv()


@dataclass
class RedditSignal:
    thread_count: int
    threads: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_reddit_client() -> praw.Reddit:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "market-scout/0.1")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET. "
            "Register a script app at https://www.reddit.com/prefs/apps and set values in .env."
        )
    return praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)


def search_complaints(
    subreddits: list[str],
    keywords: list[str],
    limit: int = 25,
    time_filter: str = "year",
) -> RedditSignal:
    """Search target subreddits for keyword-bearing posts. Returns RedditSignal."""
    reddit = _get_reddit_client()
    query = " OR ".join(keywords) if keywords else ""
    threads: list[dict[str, Any]] = []
    for sub_name in subreddits:
        try:
            for submission in reddit.subreddit(sub_name).search(
                query, sort="top", time_filter=time_filter, limit=limit
            ):
                threads.append({
                    "id": submission.id,
                    "title": submission.title,
                    "selftext": (submission.selftext or "")[:2000],
                    "score": submission.score,
                    "url": submission.url,
                    "subreddit": submission.subreddit.display_name,
                    "created_utc": submission.created_utc,
                })
        except Exception as exc:  # noqa: BLE001
            # Subreddit may be private/banned; record but don't crash
            threads.append({"error": f"{sub_name}: {exc}"})

    summary = _summarize(threads)
    return RedditSignal(thread_count=len([t for t in threads if "error" not in t]), threads=threads, summary=summary)


def _summarize(threads: list[dict[str, Any]]) -> str:
    if not threads:
        return "No complaint threads found."
    titles = [t["title"] for t in threads if "title" in t][:5]
    return "Top thread titles: " + " | ".join(titles)
