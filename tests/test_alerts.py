"""Tests for alert message formatting."""
from __future__ import annotations

from types import SimpleNamespace

from app.alerts import format_alerts


def _res(verdict: str, close: float, ticker: str = "BBRI") -> SimpleNamespace:
    return SimpleNamespace(
        verdict=verdict,
        ticker=ticker,
        plan={
            "entry_zone": {"from": 3000, "to": 3100},
            "tp1_price": 3410,
            "tp2_price": 3720,
            "stop_loss": 2914,
            "buy_avg_anchor": 3050,
        },
        technicals={"close": close},
    )


def test_format_alerts_highlights_conviction_buys():
    results = [
        _res("MAXIMUM_CONVICTION_BUY", 3100),
        _res("STRONG_BUY", 2900, "TINS"),
        _res("REJECTED", 100),
    ]
    text = format_alerts(results, lookback_days=15)
    assert "IDX Swing Scanner" in text
    assert "MAXIMUM_CONVICTION_BUY" in text
    assert "BBRI" in text
    assert "TINS" in text
    # rejected stocks are not included in the digest
    assert "REJECTED" not in text


def test_format_alerts_empty_day():
    text = format_alerts([_res("NEUTRAL_HOLD", 500)], lookback_days=10)
    assert "Tidak ada sinyal" in text