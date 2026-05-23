"""Google Trends adapter via pytrends."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import pandas as pd
from pytrends.request import TrendReq


@dataclass
class TrendsSignal:
    keyword: str
    direction: str  # "up" | "flat" | "down"
    delta_pct: float
    points: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_pytrends() -> TrendReq:
    return TrendReq(hl="en-US", tz=360)


def curve(keywords: list[str], timeframe: str = "today 5-y", geo: str = "US") -> TrendsSignal:
    """Fetch interest-over-time and classify direction as up/flat/down."""
    pt = _get_pytrends()
    pt.build_payload(keywords, timeframe=timeframe, geo=geo)
    df: pd.DataFrame = pt.interest_over_time()

    keyword = keywords[0]
    if df.empty or keyword not in df.columns:
        return TrendsSignal(keyword=keyword, direction="flat", delta_pct=0.0, points=[])

    series = df[keyword].astype(float)
    points = [{"date": idx.strftime("%Y-%m-%d"), "value": float(v)} for idx, v in series.items()]

    first_third = series.iloc[: max(1, len(series) // 3)].mean()
    last_third = series.iloc[-max(1, len(series) // 3) :].mean()
    if first_third == 0:
        delta_pct = 0.0
    else:
        delta_pct = round((last_third - first_third) / first_third * 100, 1)

    if delta_pct > 15:
        direction = "up"
    elif delta_pct < -15:
        direction = "down"
    else:
        direction = "flat"

    return TrendsSignal(keyword=keyword, direction=direction, delta_pct=delta_pct, points=points)
