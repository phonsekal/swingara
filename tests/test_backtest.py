"""Tests for the backtest engine (no network needed)."""
from __future__ import annotations

import asyncio

from app.backtest import backtest
from app.models import BacktestParams
from tests.test_scanner import CANDLES


def _bt_params(**overrides) -> BacktestParams:
    base = dict(
        tickers=["TEST"],
        lookback_days=15,
        min_history_days=60,
        retail_brokers=["YP", "CC", "NI"],
        data_source="arjum",
        max_hold_days=30,
        band_gap_max_pct=0.0,  # no band-gap cap: tuned signal bar fires (generic API path)
    )
    base.update(overrides)
    return BacktestParams(**base)


class _FakeHistory:
    """Yields the tuned signal series + continuation bars so a trade can close."""

    async def history(self, code: str, limit: int = 200, frame: str = "daily"):
        rows = [dict(c) for c in CANDLES]
        # 40 continuation bars rising steadily -> no new signals, TIMEOUT exit
        base = 950.0
        for k in range(1, 41):
            c = base + k * 1.5
            rows.append(
                {"date": f"x{k}", "open": c - 1, "high": c + 4, "low": c - 4, "close": c, "volume": 40_000_000}
            )
        return {"stock_code": code, "candles": rows}


def test_backtest_produces_trade_and_metrics():
    result = asyncio.run(backtest("TEST", _bt_params(), _FakeHistory()))
    assert "error" not in result
    assert result["metrics"]["n_trades"] == 1, result["trades"]
    assert result["trades"][0]["reason"] in ("TIMEOUT", "OPEN")
    assert result["metrics"]["total_return_pct"] is not None
    assert len(result["equity_curve"]) > 100
    assert result["n_bars"] > 100


def test_backtest_flat_series_no_trades():
    flat = [
        {"date": f"d{i}", "open": 1000.0, "high": 1005.0, "low": 995.0, "close": 1000.0, "volume": 5_000_000}
        for i in range(200)
    ]

    class FlatHistory(_FakeHistory):
        async def history(self, code: str, limit: int = 200, frame: str = "daily"):
            return {"stock_code": code, "candles": flat}

    result = asyncio.run(backtest("TEST", _bt_params(), FlatHistory()))
    assert result["metrics"]["n_trades"] == 0
    assert result["metrics"]["total_return_pct"] == 0.0
    assert result["trades"] == []