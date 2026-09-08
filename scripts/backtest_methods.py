#!/usr/bin/env python3
"""5-year backtest of every calibrated Layer A method on the liquid IDX universe.

Downloads each ticker's history ONCE (yfinance, 0 arjum quota), then replays the
backtest engine for each named method (strict / quality / main / wide) plus the
base defaults, using the same TP5/10 + SL5 + 15-day-hold blueprint.

Usage:
  .venv/bin/python scripts/backtest_methods.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest import backtest
from app.main import _combined_backtest_metrics
from app.models import BacktestParams
from app.resolve_method import SUPPORTED_METHODS
from app.scanner import _fetch_history

WATCHLIST = "BBRI,BMRI,TINS,BUMI,HRUM,BBCA,ASII,TLKM,ANTM,ADRO,PGAS,ICBP,INCO,PTBA,EXCL".split(",")
EXTRA = (
    "ACES,AMRT,MDKA,SMGR,INTP,JSMR,GGRM,KLBF,SMRA,PWON,CPIN,JPFA,AALI,LSIP,"
    "MAPI,ERAA,BRPT,TPIA,TKIM,HEAL,SILO,MIKA,GOTO,EMTK,SCMA,TBIG,TOWR,ISAT"
).split(",")
TICKERS = WATCHLIST + EXTRA

BLUEPRINT = dict(
    history_years=5,
    tp1_pct=5.0, tp2_pct=10.0, sl_pct=5.0,
    atr_stop_mult=2.0, max_hold_days=15,
    fee_pct=0.25, slippage_pct=0.1,
    start_capital=100_000_000.0, risk_per_trade_pct=2.0,
)


class CachedClient:
    """Returns pre-downloaded candles so each method reuses the same history."""

    def __init__(self, cache: dict[str, list[dict]]):
        self.cache = cache

    async def history(self, code: str, limit: int = 200, frame: str = "daily"):
        return {"stock_code": code, "candles": self.cache[code.upper()]}


def method_params(name: str, m: dict) -> BacktestParams:
    return BacktestParams(
        tickers=TICKERS,
        data_source="arjum",
        lookback_days=15,
        min_history_days=60,
        rsi_max=m["rsi_max"],
        pullback_pct=m["pullback_pct"],
        band_gap_max_pct=m["band_gap_max_pct"],
        min_price=m["min_price"],
        min_liquidity_idr=m["min_liquidity_idr"],
        touch_tolerance_pct=m["touch_tolerance_pct"],
        touch_window_days=m.get("touch_window_days", 5),
        require_close_above_ema5=m.get("require_close_above_ema5", False),
        require_green_day=m.get("require_green_day", False),
        **BLUEPRINT,
    )


async def download_all() -> dict[str, list[dict]]:
    params = BacktestParams(tickers=TICKERS, history_years=5, data_source="yfinance")
    start = (date.today() - timedelta(days=365 * 5)).isoformat()
    sem = asyncio.Semaphore(5)
    cache: dict[str, list[dict]] = {}

    async def one(t: str):
        async with sem:
            candles, _ = await _fetch_history(t, params, None, period="1y", start_date=start)
            if candles:
                cache[t] = candles

    await asyncio.gather(*(one(t) for t in TICKERS))
    return cache


def row(name: str, results: list[dict]) -> dict:
    c = _combined_backtest_metrics(results)
    n_with = sum(1 for r in results if (r.get("metrics") or {}).get("n_trades", 0) > 0)
    return {
        "set": name,
        "tickers_dgn_sinyal": f"{n_with}/{len(results)}",
        **c,
        "per_ticker": [
            {"ticker": r.get("ticker"), "n_trades": len(r.get("trades") or []),
             "total_return_pct": (r.get("metrics") or {}).get("total_return_pct")}
            for r in results
        ],
    }


async def main() -> None:
    print(f"=== BACKTEST 5 TAHUN, {len(TICKERS)} saham likuid ===", flush=True)
    cache = await download_all()
    print(f"data siap untuk {len(cache)}/{len(TICKERS)} ticker\n", flush=True)
    client = CachedClient(cache)

    configs = [
        ("base_defaults", {
            "rsi_max": 60.0, "pullback_pct": 3.0, "band_gap_max_pct": 0.0,
            "min_price": 50.0, "min_liquidity_idr": 5_000_000_000.0,
            "touch_tolerance_pct": 2.0, "touch_window_days": 5,
        }),
    ] + list(SUPPORTED_METHODS.items())
    rows: list[dict] = []
    for name, m in configs:
        params = method_params(name, m)
        results = []
        for i, t in enumerate(TICKERS, 1):
            if t not in cache:
                continue
            r = await backtest(t, params, client)
            results.append(r)
            if i % 10 == 0 or i == len(TICKERS):
                n = (r.get("metrics") or {}).get("n_trades")
                print(f"  [{name:<22}] {i}/{len(TICKERS)} {t}: trades={n}", flush=True)
        rows.append(row(name, results))
        print(flush=True)

    print("\n=== RINGKASAN 5 TAHUN ===")
    print(f"{'metode':<22}{'sinyal':>8}{'trade':>7}{'win%':>7}{'avgRet%':>9}{'PF':>7}{'maxDD%':>8}{'hold':>7}{'totRet%':>9}")
    for r in rows:
        print(
            f"{r['set']:<22}{r['tickers_dgn_sinyal']:>8}{r.get('n_trades', 0):>7}"
            f"{(r.get('win_rate_pct') or 0):>7.1f}{(r.get('avg_return_pct') or 0):>9.2f}"
            f"{str(r.get('profit_factor') or '—'):>7}{(r.get('max_drawdown_pct') or 0):>8.1f}"
            f"{(r.get('avg_hold_days') or 0):>7.1f}{'':>9}",
            flush=True,
        )

    out = Path("/tmp/backtest_methods.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nDetail tersimpan di {out}")


if __name__ == "__main__":
    asyncio.run(main())