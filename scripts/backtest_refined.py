#!/usr/bin/env python3
"""Local Layer-A backtest runner for the refined (multi-bar touch) signal.

Compares baseline vs multi-bar variant across the watchlist for a configured
history window. yfinance only — 0 arjum quota.

Usage:
  python3 scripts/backtest_refined.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest import backtest
from app.main import _combined_backtest_metrics
from app.models import BacktestParams

WATCHLIST = "BBRI,BMRI,TINS,BUMI,HRUM,BBCA,ASII,TLKM,ANTM,ADRO,PGAS,ICBP,INCO,PTBA,EXCL".split(",")

BASELINE = {
    "tp1_pct": 5.0,
    "tp2_pct": 10.0,
    "sl_pct": 5.0,
    "atr_stop_mult": 2.0,
    "max_hold_days": 15,
    "rsi_max": 60.0,
    "pullback_pct": 3.0,
    "touch_tolerance_pct": 1.0,
    "touch_window_days": 1,  # single-bar (original behaviour)
}

REFINED = {
    "tp1_pct": 5.0,
    "tp2_pct": 10.0,
    "sl_pct": 5.0,
    "atr_stop_mult": 2.0,
    "max_hold_days": 15,
    "rsi_max": 60.0,
    "pullback_pct": 3.0,
    "touch_tolerance_pct": 1.0,
    "touch_window_days": 5,  # multi-bar confirmation
}


async def run_set(tickers: list[str], overrides: dict) -> list[dict]:
    params = BacktestParams(tickers=tickers, history_years=5, **overrides)
    out: list[dict] = []
    for i, t in enumerate(tickers, 1):
        r = await backtest(t, params, None)
        out.append(r)
        print(f"  [{i}/{len(tickers)}] {t}: trades={r.get('metrics', {}).get('n_trades')} "
              f"ret={(r.get('metrics', {}).get('total_return_pct') or 0):.2f}%", flush=True)
    return out


async def main() -> None:
    print(f"=== BACKTEST REFINED vs BASELINE, 5 TAHUN, {len(WATCHLIST)} watchlist ===")
    b = await run_set(WATCHLIST, BASELINE)
    print("\n--- refined (multi-bar touch) ---")
    r = await run_set(WATCHLIST, REFINED)

    def row(name: str, results: list[dict]) -> dict:
        c = _combined_backtest_metrics(results)
        n_with_signals = sum(1 for x in results if (x.get("metrics") or {}).get("n_trades", 0) > 0)
        return {
            "set": name,
            "tickers_dgn_sinyal": f"{n_with_signals}/{len(results)}",
            **c,
            "per_ticker": [
                {"ticker": x.get("ticker"), "metrics": x.get("metrics"), "n_trades": len(x.get("trades") or [])}
                for x in results
            ],
        }

    print("\n=== RINGKASAN ===")
    labels = ["set", "tickers_dgn_sinyal", "trade", "win%", "avgRet%", "PF", "maxDD%", "hold"]
    print("\t".join(labels))
    for name, results in [("baseline (single-bar touch)", b), ("refined (multi-bar touch 5 hari)", r)]:
        row_ = row(name, results)
        print("\t".join([
            str(row_.get("set", "")),
            str(row_.get("tickers_dgn_sinyal", "")),
            str(row_.get("n_trades", 0)),
            f"{(row_.get('win_rate_pct') or 0):.1f}",
            f"{(row_.get('avg_return_pct') or 0):.2f}",
            str(row_.get("profit_factor") or "—"),
            f"{(row_.get('max_drawdown_pct') or 0):.1f}",
            f"{(row_.get('avg_hold_days') or 0):.1f}",
        ]))

    with open("/tmp/backtest_refined.json", "w") as f:
        json.dump({"baseline": b, "refined": r}, f, default=str)
    print("\nDetail tersimpan di /tmp/backtest_refined.json")


if __name__ == "__main__":
    asyncio.run(main())
