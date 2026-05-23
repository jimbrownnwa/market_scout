from unittest.mock import patch

import pytest

from scout.sources.base import SourceSignal
from scout.sources.quora import search


LONG_ANSWER = (
    "<p>Lead routing has been broken for our team for years. We've tried Salesforce flows, "
    "Distribution Engine, LeanData, and Chili Piper. Each fixes one piece and breaks another. "
    "Honestly I'd pay anything for an agent that just owns the rules end-to-end.</p>"
)


FAKE_RESPONSE = [
    {
        "id": "ans-1",
        "question": "Why is lead routing so hard at growing SaaS companies?",
        "answer": LONG_ANSWER,
        "url": "https://www.quora.com/Why-is-lead-routing-so-hard/answer/Some-One",
        "upvotes": 142,
        "date": "2026-04-10",
        "author": "Some One",
        "topic": "sales-operations",
    },
    {
        "id": "ans-stub",
        "question": "Short one",
        "answer": "Too short",  # below min_text_length
        "url": "https://www.quora.com/x",
    },
]


@patch("scout.sources.quora.run_actor")
def test_search_returns_source_signal_with_normalized_answers(mock_run):
    mock_run.return_value = FAKE_RESPONSE

    sig = search(query="lead routing", limit=10, scope=["sales-operations"])

    assert isinstance(sig, SourceSignal)
    assert sig.source == "quora"
    # The short stub should be filtered out
    assert sig.item_count == 1
    item = sig.items[0]
    assert "Lead routing has been broken" in item["text"]
    assert item["score"] == 142
    assert item["title"] == "Why is lead routing so hard at growing SaaS companies?"


@patch("scout.sources.quora.run_actor")
def test_search_passes_scope_as_topics(mock_run):
    mock_run.return_value = []
    search(query="x", scope=["sales-operations", "b2b-saas"])
    payload = mock_run.call_args.args[1]
    assert payload["topics"] == ["sales-operations", "b2b-saas"]


@patch("scout.sources.quora.run_actor")
def test_search_degrades_gracefully_on_apify_error(mock_run):
    from scout.sources._apify import ApifyError
    mock_run.side_effect = ApifyError("actor not available")
    sig = search(query="x", scope=["topic"])
    assert sig.item_count == 0
    assert "actor not available" in sig.summary
    assert any("error" in i for i in sig.items)


@patch("scout.sources.quora.run_actor")
def test_search_strips_html_from_answer(mock_run):
    mock_run.return_value = [
        {
            "id": "1",
            "question": "Q",
            "answer": "<p>foo <b>bar</b> &amp; baz</p>" + ("x" * 100),
            "url": "u",
        }
    ]
    sig = search(query="q")
    text = sig.items[0]["text"]
    assert "<" not in text
    assert "foo bar & baz" in text
