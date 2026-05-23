from unittest.mock import MagicMock, patch

import pytest

from scout.sources._apify import run_actor, ApifyError


@patch("scout.sources._apify._get_token", return_value="test-token")
@patch("scout.sources._apify.requests.post")
def test_run_actor_returns_dataset_items(mock_post, _mock_token):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"title": "a"}, {"title": "b"}],
    )
    items = run_actor("user/actor", {"keyword": "x"})
    assert items == [{"title": "a"}, {"title": "b"}]
    # URL should encode the actor id with ~
    call_args = mock_post.call_args
    assert "user~actor" in call_args.args[0]


@patch("scout.sources._apify._get_token", return_value="test-token")
@patch("scout.sources._apify.requests.post")
def test_run_actor_raises_on_http_error(mock_post, _mock_token):
    mock_post.return_value = MagicMock(status_code=500, text="server boom")
    with pytest.raises(ApifyError, match="HTTP 500"):
        run_actor("user/actor", {})


@patch("scout.sources._apify._get_token", return_value="test-token")
@patch("scout.sources._apify.requests.post")
def test_run_actor_raises_on_non_json(mock_post, _mock_token):
    bad_resp = MagicMock(status_code=200, text="not json")
    bad_resp.json.side_effect = ValueError("nope")
    mock_post.return_value = bad_resp
    with pytest.raises(ApifyError, match="not JSON"):
        run_actor("user/actor", {})


@patch.dict("os.environ", {}, clear=True)
def test_get_token_raises_when_missing():
    from scout.sources._apify import _get_token
    with pytest.raises(ApifyError, match="Missing APIFY_TOKEN"):
        _get_token()
