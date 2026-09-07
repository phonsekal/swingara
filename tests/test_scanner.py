"""End-to-end tests for the scanner verdict engine (no network needed)."""
from __future__ import annotations

import asyncio

from app.models import ScanParams
from app.scanner import _layer_bc, analyze_stock


def _candles() -> list[dict]:
    """Strong uptrend (100 -> 1000), 18-bar pullback to ~932, then a hammer bar
    whose low touches the lower Bollinger band while close stays above EMA20."""
    rows: list[dict] = []
    for i in range(100):
        close = 100.0 + i * 9.0
        rows.append(
            {
                "date": f"d{i}",
                "open": close - 4,
                "high": close + 12,
                "low": close - 10,
                "close": close,
                "volume": 50_000_000,
            }
        )
    for k in range(1, 19):
        close = 1000.0 - k * 3.8
        rows.append(
            {
                "date": f"p{k}",
                "open": close + 3,
                "high": close + 8,
                "low": close - 6,
                "close": close,
                "volume": 50_000_000,
            }
        )
    rows.append(
        {
            "date": "last",
            "open": 932.0,
            "high": 957.0,
            "low": 922.0,
            "close": 950.0,
            "volume": 55_000_000,
        }
    )
    return rows


CANDLES = _candles()


def _broker_rows() -> list[dict]:
    return [
        {"broker_code": "SS", "broker_name": "Supra Sekuritas Indonesia", "bval": 120e9, "sval": 20e9, "nval": 100e9, "nvol": 1e6},
        {"broker_code": "BK", "broker_name": "J.P. Morgan Sekuritas", "bval": 90e9, "sval": 30e9, "nval": 60e9, "nvol": 6e5},
        {"broker_code": "ZP", "broker_name": "Maybank Sekuritas", "bval": 40e9, "sval": 10e9, "nval": 30e9, "nvol": 3e5},
        {"broker_code": "AG", "broker_name": "Kiwoom Sekuritas", "bval": 10e9, "sval": 40e9, "nval": -30e9, "nvol": -4e5},
        {"broker_code": "YP", "broker_name": "Yugen Berkah Sekuritas", "bval": 5e9, "sval": 55e9, "nval": -50e9, "nvol": -5e5},
        {"broker_code": "CC", "broker_name": "CGS-CIMB Sekuritas", "bval": 4e9, "sval": 24e9, "nval": -20e9, "nvol": -2e5},
    ]


class FakeArjum:
    """Duck-typed stand-in for ArjumClient (async methods, no network)."""

    def __init__(self, broker_rows: list[dict] | None = None):
        self.broker_rows = broker_rows if broker_rows is not None else _broker_rows()

    async def history(self, code: str, limit: int = 200, frame: str = "daily"):
        return {"stock_code": code, "candles": CANDLES}

    async def broker_summary(self, code, start_date, end_date, broker_limit=20, flow="all", net=False):
        return {
            "stock_code": code,
            "flow": flow,
            "broker_start": start_date,
            "broker_end": end_date,
            "brokers": self.broker_rows,
        }


def _params(**overrides) -> ScanParams:
    base = dict(
        tickers=["TEST"],
        lookback_days=15,
        min_history_days=60,
        retail_brokers=["YP", "CC", "NI"],
        data_source="arjum",  # use FakeArjum for history (default is yfinance-first)
    )
    base.update(overrides)
    return ScanParams(**base)


def test_full_conviction_buy_with_default_broker_mode():
    verdict = asyncio.run(analyze_stock("TEST", _params(), FakeArjum()))
    assert verdict.verdict == "MAXIMUM_CONVICTION_BUY", verdict.layers
    assert verdict.layers["a"]["status"] == "pass"
    assert verdict.layers["b"]["status"] == "pass"
    assert verdict.layers["c"]["status"] == "pass"
    assert verdict.plan is not None
    # backtest-backed plan defaults
    assert verdict.plan["tp1_pct"] == 5.0
    assert verdict.plan["tp2_pct"] == 10.0
    assert verdict.plan["sl_pct"] == 5.0
    # SS detected as one of the matched institutional brokers in loose mode
    matched = [b["broker_code"] for b in verdict.broker_flow["layer_b"]["details"]["matched_brokers"]]
    assert "SS" in matched


def test_broker_filter_pinned_broker_absent_gives_neutral_hold():
    # Pinned broker "XZ" is not a top buyer -> Layer B fails -> NEUTRAL_HOLD,
    # even though other brokers (BK/ZP) are accumulating.
    verdict = asyncio.run(analyze_stock("TEST", _params(brokers=["XZ"]), FakeArjum()))
    assert verdict.verdict == "NEUTRAL_HOLD", verdict.layers
    assert verdict.layers["b"]["status"] == "fail"


def test_broker_filter_with_ss_present_passes_layer_b():
    verdict = asyncio.run(analyze_stock("TEST", _params(brokers=["SS"]), FakeArjum()))
    assert verdict.verdict == "MAXIMUM_CONVICTION_BUY", verdict.layers


def test_anchor_chase_protection_rejects_overextended_price():
    # Crafted candles: price has run 1000 > vwap(15) ~911 while SS is top buyer.
    candles = [
        {"date": f"d{i}", "open": 900.0, "high": 905.0, "low": 895.0, "close": 900.0, "volume": 1e7}
        for i in range(100)
    ]
    candles += [
        {"date": "r1", "open": 900.0, "high": 922.0, "low": 898.0, "close": 920.0, "volume": 1e7},
        {"date": "r2", "open": 920.0, "high": 952.0, "low": 918.0, "close": 950.0, "volume": 1e7},
        {"date": "r3", "open": 950.0, "high": 1002.0, "low": 948.0, "close": 1000.0, "volume": 1e7},
    ]
    raw = {
        "stock_code": "TEST",
        "brokers": _broker_rows(),
    }
    b, _ = _layer_bc(raw, candles, _params(price_anchor_pct=3.0))
    assert b["status"] == "fail"
    assert b["details"]["price_anchor_ok"] is False


def test_retail_sellers_missing_caps_to_strong_buy():
    rows = [r for r in _broker_rows() if r["broker_code"] not in ("YP", "CC")]
    verdict = asyncio.run(analyze_stock("TEST", _params(), FakeArjum(rows)))
    assert verdict.verdict == "STRONG_BUY", verdict.layers
    assert verdict.layers["c"]["status"] == "fail"


def test_no_broker_data_gives_watchlist(monkeypatch):
    async def fake_yf(code: str, bars: int = 0, period: str = "1y", start_date: str | None = None):
        return CANDLES

    monkeypatch.setattr("app.scanner._history_from_yfinance", fake_yf)
    verdict = asyncio.run(analyze_stock("TEST", _params(), None))
    assert verdict.verdict == "WATCHLIST", verdict.layers
    assert verdict.plan is not None  # Layer A still passed -> blueprint provided


def test_rejected_when_technicals_fail():
    bad = [
        {"date": f"d{i}", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1e6}
        for i in range(200)
    ]

    class FlatHistory(FakeArjum):
        async def history(self, code, limit=200, frame="daily"):
            return {"stock_code": code, "candles": bad}

    verdict = asyncio.run(analyze_stock("TEST", _params(), FlatHistory()))
    assert verdict.verdict == "REJECTED"
    assert verdict.plan is None