from unittest.mock import patch

import pytest

from scout.sources.base import SourceSignal
from scout.sources.g2 import search


FAKE_RESPONSE = [
    {
        "id": "rev-1",
        "title": "Constantly breaking",
        "body": "We've been on this tool for 2 years and it still doesn't handle multi-touch routing.",
        "cons": "Confusing UI. Constantly breaks. Support is unresponsive.",
        "switchReason": "We're moving to a competitor because we lost trust.",
        "url": "https://www.g2.com/products/x/reviews/rev-1",
        "rating": 2,
        "date": "2026-03-02",
        "reviewer": "Anonymous RevOps Manager",
        "product": "ExampleTool",
        "category": "sales-engagement",
    },
    {
        "id": "rev-2",
        "title": "Wouldn't recommend",
        "body": "Onboarding took 3 months. Still don't see ROI.",
        "cons": "Slow, buggy, terrible reporting.",
        "url": "https://www.g2.com/products/x/reviews/rev-2",
        "rating": 1,
        "date": "2026-02-15",
        "product": "ExampleTool",
    },
    {
        "id": "rev-positive",
        "title": "Love it",
        "body": "Best tool ever",
        "rating": 5,  # should be filtered out by max_stars threshold
        "url": "https://www.g2.com/products/x/reviews/rev-positive",
    },
]


@patch("scout.sources.g2.run_actor")
def test_search_returns_source_signal_with_normalized_reviews(mock_run):
    mock_run.return_value = FAKE_RESPONSE

    sig = search(query="lead routing", limit=10, scope=["sales-engagement"])

    assert isinstance(sig, SourceSignal)
    assert sig.source == "g2"
    # 5-star review should be filtered out
    assert sig.item_count == 2
    assert any("Constantly breaking" in i.get("title", "") for i in sig.items if "error" not in i)
    # Cons + switch reason should be included in text
    first_text = sig.items[0]["text"]
    assert "Confusing UI" in first_text
    assert "moving to a competitor" in first_text


@patch("scout.sources.g2.run_actor")
def test_search_passes_scope_as_categories(mock_run):
    mock_run.return_value = []
    search(query="x", scope=["sales-engagement", "lead-routing"])
    payload = mock_run.call_args.args[1]
    assert payload["categories"] == ["sales-engagement", "lead-routing"]


@patch("scout.sources.g2.run_actor")
def test_search_degrades_gracefully_on_apify_error(mock_run):
    from scout.sources._apify import ApifyError
    mock_run.side_effect = ApifyError("rate limited")
    sig = search(query="x", scope=["cat"])
    assert sig.item_count == 0
    assert "rate limited" in sig.summary
    assert any("error" in i for i in sig.items)


@patch("scout.sources.g2.run_actor")
def test_search_respects_custom_max_stars(mock_run):
    mock_run.return_value = [
        {"id": "1", "rating": 2, "title": "bad", "body": "x"},
        {"id": "2", "rating": 4, "title": "ok", "body": "y"},
    ]
    sig = search(query="x", max_stars=2)
    assert sig.item_count == 1
    assert sig.items[0]["title"] == "bad"
