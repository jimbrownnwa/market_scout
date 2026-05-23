from unittest.mock import MagicMock, patch

import pytest

from scout.sources.base import SourceSignal
from scout.sources.hackernews import search, _strip_html


FAKE_STORY_HITS = {
    "hits": [
        {
            "objectID": "11111",
            "title": "Ask HN: How do you handle lead routing chaos?",
            "story_text": "<p>We tried 3 tools and none stick.</p>",
            "url": None,
            "points": 142,
            "num_comments": 47,
            "created_at": "2026-04-18T10:00:00Z",
            "author": "exampleuser",
        }
    ]
}

FAKE_COMMENT_HITS = {
    "hits": [
        {
            "objectID": "22222",
            "comment_text": "<p>Honestly, I'd pay anything to fix this. It's been broken for 5 years and every tool has the same gap.</p>",
            "created_at": "2026-04-18T11:00:00Z",
            "author": "commenter",
        }
    ]
}


def _make_mock_response(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status = MagicMock()
    return m


@patch("scout.sources.hackernews.requests.get")
def test_search_returns_source_signal_with_stories_and_comments(mock_get):
    def side_effect(url, params=None, timeout=None):
        if params and params.get("tags", "").startswith("comment,"):
            return _make_mock_response(FAKE_COMMENT_HITS)
        return _make_mock_response(FAKE_STORY_HITS)

    mock_get.side_effect = side_effect

    sig = search(query="lead routing chaos", limit=10)

    assert isinstance(sig, SourceSignal)
    assert sig.source == "hackernews"
    assert sig.item_count >= 1
    titles = [i.get("title", "") for i in sig.items]
    assert any("lead routing" in t.lower() for t in titles)
    # Should also pull at least one comment
    assert any("pay anything" in i.get("text", "").lower() for i in sig.items)


@patch("scout.sources.hackernews.requests.get")
def test_search_handles_http_error_gracefully(mock_get):
    import requests as req
    mock_get.side_effect = req.RequestException("network down")
    sig = search(query="zzz", limit=5)
    assert sig.item_count == 0
    assert any("error" in i for i in sig.items)


@patch("scout.sources.hackernews.requests.get")
def test_search_ignores_scope_argument(mock_get):
    mock_get.return_value = _make_mock_response({"hits": []})
    sig = search(query="x", scope=["does-not-matter"])
    # No exceptions, scope simply unused
    assert sig.source == "hackernews"


def test_strip_html_removes_tags_and_unescapes_entities():
    assert _strip_html("<p>hello &amp; world</p>") == "hello & world"
    assert _strip_html("<b>foo</b><br/><i>bar</i>") == "foo bar"


@patch("scout.sources.hackernews.requests.get")
def test_search_sorts_items_by_engagement(mock_get):
    payload = {
        "hits": [
            {"objectID": "1", "title": "low", "points": 5, "num_comments": 2, "story_text": ""},
            {"objectID": "2", "title": "high", "points": 200, "num_comments": 50, "story_text": ""},
        ]
    }
    mock_get.return_value = _make_mock_response(payload)
    sig = search(query="x", include_comments=False)
    assert sig.items[0]["title"] == "high"
