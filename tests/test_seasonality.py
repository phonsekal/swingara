"""Tests for the local monthly seasonality computation."""
from __future__ import annotations

from datetime import date, timedelta

from app.seasonality import monthly_seasonality


def _year_of_daily_candles(year: int, closes: dict[int, float]) -> list[dict]:
    """Closes per month-end + flat daily bars between, for one year."""
    candles = []
    for month in range(1, 13):
        days_in_month = 28 if month == 2 else 30
        target_close = closes.get(month, 100.0)
        for day in range(1, days_in_month + 1):
            d = date(year, month, min(day, 28))
            candles.append({"date": d.isoformat(), "close": 100.0})
        # overwrite month-end with the desired close
        candles[-1]["close"] = target_close
    return candles


def test_seasonality_picks_best_and_worst_month():
    candles = []
    # 3 years: January always up strongly, July always down, rest flat
    # (months after Jul stay at the dip so Jan's +50% stays the biggest).
    closes = {1: 120.0, 7: 80.0, 8: 80.0, 9: 80.0, 10: 80.0, 11: 80.0, 12: 80.0}
    for y in (2024, 2025, 2026):
        candles += _year_of_daily_candles(y, closes)
    res = monthly_seasonality(candles, max_years=8)
    assert res is not None
    assert res["best_month"] == 1
    assert res["worst_month"] == 7
    assert res["years_analyzed"] == 3
    jan = res["months"][0]
    assert jan["avg_return_pct"] > 10
    assert jan["win_rate_pct"] == 100


def test_seasonality_returns_none_for_short_history():
    short = [{"date": f"2026-01-{d:02d}", "close": 100.0} for d in range(1, 30)]
    assert monthly_seasonality(short) is None