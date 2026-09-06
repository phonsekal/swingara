"""Monthly seasonality computed from local OHLCV history (0 arjum quota).

For each calendar month we take the last close of that month vs the last close of
the previous month -> monthly return -> aggregate average return & win rate.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def monthly_seasonality(candles: list[dict], max_years: int = 8) -> Optional[dict]:
    if len(candles) < 400:  # need ~1.5+ years of bars
        return None

    month_close: dict[tuple[int, int], float] = {}
    for c in candles:
        try:
            d = datetime.strptime(c["date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        # later rows win -> last close of the month
        month_close[(d.year, d.month)] = float(c["close"])

    items = sorted(month_close.items())
    returns: dict[tuple[int, int], float] = {}
    for i in range(1, len(items)):
        (y, m), close = items[i]
        (py, pm), prev_close = items[i - 1]
        if close > 0 and prev_close > 0:
            returns[(y, m)] = (close / prev_close - 1.0) * 100.0

    if not returns:
        return None
    max_year = max(y for (y, _) in returns)
    returns = {k: v for k, v in returns.items() if k[0] >= max_year - max_years + 1}
    if len(returns) < 12:
        return None

    months: list[dict] = []
    for m in range(1, 13):
        vals = [v for (y, mm), v in returns.items() if mm == m]
        if not vals:
            months.append({"month": m, "avg_return_pct": None, "win_rate_pct": None, "n": 0})
            continue
        months.append(
            {
                "month": m,
                "avg_return_pct": round(sum(vals) / len(vals), 2),
                "win_rate_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100.0, 0),
                "n": len(vals),
            }
        )

    valid = [x for x in months if x["avg_return_pct"] is not None]
    best = max(valid, key=lambda x: x["avg_return_pct"])
    worst = min(valid, key=lambda x: x["avg_return_pct"])
    return {
        "months": months,
        "best_month": best["month"],
        "best_avg_pct": best["avg_return_pct"],
        "worst_month": worst["month"],
        "worst_avg_pct": worst["avg_return_pct"],
        "years_analyzed": len({y for (y, _) in returns}),
        "source": "yfinance (lokal)",
    }