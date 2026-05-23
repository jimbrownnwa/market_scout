from unittest.mock import patch

import pytest

from scout.sources.reddit import search
from scout.sources.base import SourceSignal


FAKE_RESPONSE = [
    {
        "id": "abc1",
        "title": "Lead routing is killing me",
        "body": "We tried 3 tools and none stick...",
        "url": "https://reddit.com/r/revops/abc1",
        "upVotes": 142,
        "createdAt": "2026-04-18T10:00:00Z",
        "username": "u/example",
        "communityName": "revops",
        "numberOfComments": 47,
    },
    {
        "id": "abc2",
        "title": "I'd pay anything to fix attribution",
        "selftext": "5 years of this problem...",
        "url": "https://reddit.com/r/revops/abc2",
        "score": 89,
        "createdAt": "2026-04-12T09:00:00Z",
        "username": "u/another",
        "subreddit": "revops",
        "num_comments": 31,
    },
]


@patch("scout.sources.reddit.run_actor")
def test_search_returns_source_signal_with_normalized_items(mock_run):
    mock_run.return_value = FAKE_RESPONSE

    sig = search(query="lead routing", limit=5, scope=["revops"])

    assert isinstance(sig, SourceSignal)
    assert sig.source == "reddit"
    assert sig.query == "lead routing"
    assert sig.item_count == 2
    assert sig.items[0]["title"] == "Lead routing is killing me"
    assert sig.items[0]["url"].startswith("https://reddit.com/")
    assert sig.items[0]["score"] == 142
    assert sig.items[0]["subreddit"] == "revops"
    assert "killing" in sig.summary.lower()


@patch("scout.sources.reddit.run_actor")
def test_search_handles_empty_results(mock_run):
    mock_run.return_value = []
    sig = search(query="zzz", scope=["nothing"])
    assert sig.item_count == 0
    assert sig.items == []
    assert "No reddit" in sig.summary


@patch("scout.sources.reddit.run_actor")
def test_search_normalizes_selftext_to_text_field(mock_run):
    mock_run.return_value = [{"id": "x", "title": "T", "selftext": "body here", "url": "u"}]
    sig = search(query="q")
    assert sig.items[0]["text"] == "body here"


@patch("scout.sources.reddit.run_actor")
def test_search_degrades_gracefully_on_apify_error(mock_run):
    from scout.sources._apify import ApifyError
    mock_run.side_effect = ApifyError("boom")
    sig = search(query="q", scope=["revops"])
    assert sig.item_count == 0
    assert "boom" in sig.summary
    assert any("error" in item for item in sig.items)


@patch("scout.sources.reddit.run_actor")
def test_search_builds_subreddit_specific_start_urls(mock_run):
    mock_run.return_value = []
    search(query="lead routing", scope=["revops", "saas"])
    payload = mock_run.call_args.args[1]
    urls = [u["url"] for u in payload["startUrls"]]
    assert any("/r/revops/" in u for u in urls)
    assert any("/r/saas/" in u for u in urls)


@patch("scout.sources.reddit.run_actor")
def test_search_falls_back_to_global_when_no_scope(mock_run):
    mock_run.return_value = []
    search(query="lead routing")
    payload = mock_run.call_args.args[1]
    assert "/search/" in payload["startUrls"][0]["url"]
