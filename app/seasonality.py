'''
Monthly seasonality with real monthly bars for chart and summary.

Two modes:
- summary: aggregate avg return and win rate per calendar month, with best/worst
  month across the period.
- chart data: return the real monthly series (month, year, close, monthly_return_pct)
  for the last N years, so the frontend can render a proper bar chart.

Both are derived from the same multi-year yfinance history (0 arjum quota).
'''
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def _round2(v: float) -> Optional[float]:
    if v is None:
        return None
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def monthly_seasonality(
    candles: list[dict],
    max_years: int = 8,
    *,
    chart_years: int = 5,
) -> Optional[dict]:
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
    prev_close: Optional[float] = None
    prev_key: Optional[tuple[int, int]] = None
    for (y, m), close in items:
        if prev_close is not None and close > 0 and prev_close > 0:
            returns[(y, m)] = (close / prev_close - 1.0) * 100.0
        prev_close = close
        prev_key = (y, m)

    if not returns:
        return None

    max_year = max(y for (y, _) in returns)
    summary_returns = {k: v for k, v in returns.items() if k[0] >= max_year - max_years + 1}
    if len(summary_returns) < 12:
        return None

    months: list[dict] = []
    for m in range(1, 13):
        vals = [v for (y, mm), v in summary_returns.items() if mm == m]
        if not vals:
            months.append({"month": m, "avg_return_pct": None, "win_rate_pct": None, "n": 0})
            continue
        months.append(
            {
                "month": m,
                "avg_return_pct": _round2(sum(vals) / len(vals)),
                "win_rate_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100.0, 0),
                "n": len(vals),
            }
        )

    valid = [x for x in months if x["avg_return_pct"] is not None]
    best = max(valid, key=lambda x: x["avg_return_pct"])
    worst = min(valid, key=lambda x: x["avg_return_pct"])

    # Real monthly bar series for chart (last chart_years)
    chart_items = sorted(returns.keys())
    chart_items = [k for k in chart_items if k[0] >= max_year - chart_years + 1]
    chart_series: list[dict] = []
    prev = None
    for (y, m) in chart_items:
        cur = returns.get((y, m))
        if cur is None:
            continue
        chart_series.append(
            {
                "year": y,
                "month": m,
                "label": f"{m:02d}\n{y}",
                "close": round(month_close.get((y, m), 0.0), 2),
                "monthly_return_pct": _round2(cur),
            }
        )
        prev = (y, m)

    return {
        "months": months,
        "best_month": best["month"],
        "best_avg_pct": best["avg_return_pct"],
        "worst_month": worst["month"],
        "worst_avg_pct": worst["avg_return_pct"],
        "years_analyzed": len({y for (y, _) in summary_returns}),
        "source": "yfinance (lokal)",
        "chart": {
            "years_requested": chart_years,
            "monthly_bars": chart_series,
            "start_year": chart_series[0]["year"] if chart_series else None,
            "end_year": chart_series[-1]["year"] if chart_series else None,
        },
    }