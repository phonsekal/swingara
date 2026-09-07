"""Quick, interpretable parameter tuning (watchlist, 5y). Not curve-fitting —
only simple, explainable alternatives."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest import backtest
from app.main import _combined_backtest_metrics
from app.models import BacktestParams

WATCHLIST = "BBRI,BMRI,TINS,BUMI,HRUM,BBCA,ASII,TLKM,ANTM,ADRO,PGAS,ICBP,INCO,PTBA,EXCL".split(",")

VARIANTS = {
    "A baseline": {},
    "B TP5/10 SL5 hold15": {"tp1_pct": 5.0, "tp2_pct": 10.0, "sl_pct": 5.0, "max_hold_days": 15},
    "C TP8/15 SL6 hold20": {"tp1_pct": 8.0, "tp2_pct": 15.0, "sl_pct": 6.0, "max_hold_days": 20},
    "D TP6/12 SL4 hold10 (cepat)": {"tp1_pct": 6.0, "tp2_pct": 12.0, "sl_pct": 4.0, "max_hold_days": 10},
    "E TP12/25 SL8 hold45 (swing besar)": {"tp1_pct": 12.0, "tp2_pct": 25.0, "sl_pct": 8.0, "max_hold_days": 45},
    "F fee 0.15%": {"fee_pct": 0.15},
    "G rsi65 pull2 (lebih banyak sinyal)": {"rsi_max": 65.0, "pullback_pct": 2.0},
    "H stop ketat atr1.5 sl3": {"atr_stop_mult": 1.5, "sl_pct": 3.0, "max_hold_days": 15},
}


async def run_set(tickers: list[str], overrides: dict) -> list[dict]:
    params = BacktestParams(tickers=tickers, history_years=5, **overrides)
    return [await backtest(t, params, None) for t in tickers]


async def main() -> None:
    print(f"=== TUNING 5 TAHUN, {len(WATCHLIST)} saham watchlist ===")
    results = {}
    for name, over in VARIANTS.items():
        res = await run_set(WATCHLIST, over)
        results[name] = res
        c = _combined_backtest_metrics(res)
        print(f"{name:<26} trade={c.get('n_trades',0):>4} win={(c.get('win_rate_pct') or 0):>5.1f}% "
              f"avgRet={(c.get('avg_return_pct') or 0):>6.2f}% PF={str(c.get('profit_factor')):>5} "
              f"maxDD={(c.get('max_drawdown_pct') or 0):>5.1f}% hold={(c.get('avg_hold_days') or 0):>4.1f}", flush=True)

    with open("/tmp/tune_results.json", "w") as f:
        import json
        json.dump({k: [{"ticker": r.get("ticker"), "metrics": r.get("metrics"), "trades": r.get("trades")} for r in v]
                   for k, v in results.items()}, f, default=str)


if __name__ == "__main__":
    asyncio.run(main())