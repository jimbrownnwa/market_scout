from unittest.mock import MagicMock, patch

import pytest

from scout.sources.reddit import search_complaints, RedditSignal


def _fake_submission(title, selftext, score, url, subreddit, created_utc):
    sub = MagicMock()
    sub.title = title
    sub.selftext = selftext
    sub.score = score
    sub.url = url
    sub.subreddit = MagicMock()
    sub.subreddit.display_name = subreddit
    sub.created_utc = created_utc
    sub.id = url.split("/")[-1]
    return sub


@patch("scout.sources.reddit._get_reddit_client")
def test_search_complaints_returns_signal_summary(mock_client):
    fake_reddit = MagicMock()
    fake_reddit.subreddit.return_value.search.return_value = [
        _fake_submission("Lead routing is killing me", "We tried 3 tools...", 142, "https://reddit.com/r/revops/1", "revops", 1716_000_000),
        _fake_submission("I'd pay anything to fix attribution", "...", 89, "https://reddit.com/r/revops/2", "revops", 1716_100_000),
    ]
    mock_client.return_value = fake_reddit

    signal: RedditSignal = search_complaints(["revops"], keywords=["routing", "attribution"], limit=5)

    assert signal.thread_count == 2
    assert len(signal.threads) == 2
    assert signal.threads[0]["title"] == "Lead routing is killing me"
    assert "killing" in signal.summary.lower() or signal.thread_count == 2


@patch("scout.sources.reddit._get_reddit_client")
def test_search_complaints_handles_empty_results(mock_client):
    fake_reddit = MagicMock()
    fake_reddit.subreddit.return_value.search.return_value = []
    mock_client.return_value = fake_reddit

    signal = search_complaints(["nonexistent"], keywords=["xyz"], limit=5)
    assert signal.thread_count == 0
    assert signal.threads == []
