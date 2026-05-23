from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scout.sources.trends import curve, TrendsSignal


def _fake_df(values, dates):
    return pd.DataFrame({"revops": values}, index=pd.to_datetime(dates))


@patch("scout.sources.trends._get_pytrends")
def test_curve_returns_direction_up(mock_pytrends):
    pt = MagicMock()
    pt.interest_over_time.return_value = _fake_df(
        values=[10, 20, 40, 60, 80],
        dates=["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
    )
    mock_pytrends.return_value = pt

    sig: TrendsSignal = curve(["revops"], timeframe="today 5-y")
    assert sig.direction == "up"
    assert sig.delta_pct > 0
    assert len(sig.points) == 5


@patch("scout.sources.trends._get_pytrends")
def test_curve_returns_direction_down(mock_pytrends):
    pt = MagicMock()
    pt.interest_over_time.return_value = _fake_df(
        values=[80, 60, 40, 20, 10],
        dates=["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
    )
    mock_pytrends.return_value = pt

    sig = curve(["revops"], timeframe="today 5-y")
    assert sig.direction == "down"
    assert sig.delta_pct < 0


@patch("scout.sources.trends._get_pytrends")
def test_curve_handles_flat(mock_pytrends):
    pt = MagicMock()
    pt.interest_over_time.return_value = _fake_df(
        values=[50, 51, 50, 49, 50],
        dates=["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
    )
    mock_pytrends.return_value = pt

    sig = curve(["revops"], timeframe="today 5-y")
    assert sig.direction == "flat"
