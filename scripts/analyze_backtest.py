"""Multi-year strategy analysis: baseline + parameter sensitivity.

Usage: .venv/bin/python scripts/analyze_backtest.py
(yfinance only — 0 arjum quota.)
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
EXTRA = (
    "ACES,AMRT,MDKA,SMGR,INTP,JSMR,GGRM,KLBF,SMRA,PWON,CPIN,JPFA,AALI,LSIP,"
    "MAPI,ERAA,BRPT,TPIA,TKIM,HEAL,SILO,MIKA,GOTO,EMTK,SCMA,TBIG,TOWR,ISAT"
).split(",")

VARIANTS = {
    "baseline (default)": {},
    "rsi_max=50 (lebih ketat)": {"rsi_max": 50.0},
    "pullback=5% (koreksi lebih dalam)": {"pullback_pct": 5.0},
    "SL=8%, ATR=3 (stop lebih longgar)": {"sl_pct": 8.0, "atr_stop_mult": 3.0},
    "lookback=10 hari": {"lookback_days": 10},
    "likuiditas 10M": {"min_liquidity_idr": 10_000_000_000.0},
}


async def run_set(tickers: list[str], overrides: dict) -> list[dict]:
    params = BacktestParams(tickers=tickers, history_years=5, **overrides)
    results: list[dict] = []
    for i, t in enumerate(tickers, 1):
        r = await backtest(t, params, None)
        results.append(r)
        print(f"  [{i}/{len(tickers)}] {t}: trades={r.get('metrics', {}).get('n_trades')} "
              f"ret={r.get('metrics', {}).get('total_return_pct')}%", flush=True)
    return results


async def main() -> None:
    full = WATCHLIST + EXTRA
    print(f"=== BACKTEST 5 TAHUN, {len(full)} saham likuid ===")
    baseline = await run_set(full, {})

    print("\n=== SENSITIVITAS PARAMETER (watchlist 15 saham) ===")
    variant_sets: dict[str, list[dict]] = {}
    for name, over in VARIANTS.items():
        if name == "baseline (default)":
            variant_sets[name] = await run_set(WATCHLIST, {})
        else:
            print(f"\n-- {name} --")
            variant_sets[name] = await run_set(WATCHLIST, over)

    def table(name: str, results: list[dict]) -> dict:
        c = _combined_backtest_metrics(results)
        n = sum(1 for r in results if r.get("metrics", {}).get("n_trades", 0) > 0)
        return {"set": name, "tickers_dgn_sinyal": f"{n}/{len(results)}", **c}

    print("\n=== RINGKASAN ===")
    print(f"{'set':<28}{'trade':>7}{'win%':>7}{'avgRet%':>9}{'PF':>7}{'maxDD%':>8}{'hold':>7}")
    rows = [table("baseline 43 saham", baseline)]
    for name, res in variant_sets.items():
        rows.append(table(name, res))
    for r in rows:
        print(f"{r['set']:<28}{r.get('n_trades', 0):>7}{(r.get('win_rate_pct') or 0):>7.1f}"
              f"{(r.get('avg_return_pct') or 0):>9.2f}{str(r.get('profit_factor') or '—'):>7}"
              f"{(r.get('max_drawdown_pct') or 0):>8.1f}{(r.get('avg_hold_days') or 0):>7.1f}")

    with open("/tmp/backtest_analysis.json", "w") as f:
        json.dump({"baseline": baseline, "variants": {k: v for k, v in variant_sets.items()}}, f, default=str)
    print("\nDetail tersimpan di /tmp/backtest_analysis.json")


if __name__ == "__main__":
    asyncio.run(main())