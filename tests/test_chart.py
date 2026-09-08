"""Tests for the weekly chart builder (BB / MACD / EMA5/21 + golden cross)."""
from __future__ import annotations

from datetime import date, timedelta

from app.chart import build_weekly_chart


def _daily_candles(closes: list[float]) -> list[dict]:
    """Turn a list of daily closes into OHLCV candles starting 2021-01-04."""
    out: list[dict] = []
    d = date(2021, 1, 4)
    for c in closes:
        out.append(
            {
                "date": d.isoformat(),
                "open": c - 0.5,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1_000_000,
            }
        )
        d += timedelta(days=1)
    return out


def test_build_weekly_chart_returns_series_aligned_to_weekly_candles():
    closes = [100.0] * 260 + [100.0 + i * 2.0 for i in range(1, 80)]
    chart = build_weekly_chart(_daily_candles(closes), max_bars=120)
    assert chart is not None
    assert chart["frame"] == "1W"
    n = len(chart["candles"])
    assert 40 <= n <= 120
    # weekly close == last daily close of that week
    assert chart["candles"][-1]["close"] == closes[-1]
    for key in ("bb_upper", "bb_mid", "bb_lower", "ema5", "ema21", "macd_line", "macd_signal", "macd_hist"):
        assert len(chart[key]) == n, key
    # indicators must be populated on the latest bars
    assert chart["last"]["close"] == round(closes[-1], 2)
    assert chart["last"]["ema5"] is not None
    assert chart["last"]["ema21"] is not None
    assert chart["last"]["bb_lower"] is not None
    assert chart["last"]["macd"] is not None


def test_golden_cross_detected_after_uptrend():
    # flat for a long time, then a strong rally -> EMA5 crosses above EMA21
    closes = [100.0] * 220 + [100.0 + i * 8.0 for i in range(1, 90)]
    chart = build_weekly_chart(_daily_candles(closes), max_bars=120)
    assert chart is not None
    assert chart["golden_cross"] is not None
    gc = chart["golden_cross"]
    assert gc["date"]  # a real date string
    assert gc["ema5"] > gc["ema21"]  # cross bar: EMA5 above EMA21
    assert chart["ema5_above_ema21"] is True


def test_fresh_golden_cross_flagged_when_recent():
    # short rally at the very end of the series -> cross happened 1-2 weeks ago
    closes = [100.0] * 220 + [100.0 + i * 8.0 for i in range(1, 15)]
    chart = build_weekly_chart(_daily_candles(closes), max_bars=120)
    assert chart is not None
    assert chart["golden_cross"] is not None
    assert chart["golden_cross"]["fresh"] is True
    assert chart["golden_cross"]["bars_since"] <= 2


def test_no_golden_cross_on_steady_downtrend():
    closes = [300.0 - i * 1.0 for i in range(300)]  # relentless downtrend
    chart = build_weekly_chart(_daily_candles(closes), max_bars=120)
    assert chart is not None
    # EMA5 stays below EMA21 — no bullish cross on this window
    assert chart["golden_cross"] is None
    assert chart["ema5_above_ema21"] is False


def test_chart_returns_none_when_history_too_short():
    assert build_weekly_chart(_daily_candles([100.0] * 20)) is None