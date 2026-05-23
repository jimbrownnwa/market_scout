"""Shared types for pain-signal source adapters.

Every source module (reddit, hackernews, g2, quora) exposes the same shape:

    search(query: str, limit: int = 25, scope: list[str] | None = None) -> SourceSignal

`scope` is interpreted per source (subreddits for reddit, software categories
for g2, topics for quora, ignored for hackernews).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SourceSignal:
    source: str
    query: str
    item_count: int
    items: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_items(items: list[dict[str, Any]], source: str) -> str:
    """One-line summary listing up to 5 titles (or first 80 chars of text if no title)."""
    if not items:
        return f"No {source} results found."
    snippets: list[str] = []
    for item in items[:5]:
        if "error" in item:
            continue
        title = item.get("title") or ""
        if not title:
            title = (item.get("text") or "")[:80]
        if title:
            snippets.append(title)
    if not snippets:
        return f"No {source} results found."
    return f"Top {source} results: " + " | ".join(snippets)
