"""Weekly (1W) candle chart data with BB(20,2), MACD(12,26,9) and EMA5/EMA21.

Built from the same daily history already downloaded for the scan (0 extra
arjum quota): daily bars are resampled to weekly bars, indicators are computed
on the weekly closes, and EMA5/EMA21 golden crosses are detected so the UI can
raise an alert when a fresh bullish cross happens.

Payload shape (all series are aligned to the weekly candles, NaN -> null):
{
  "frame": "1W",
  "candles": [{date, open, high, low, close, volume}, ...],
  "bb_upper"/"bb_mid"/"bb_lower": [...],
  "ema5"/"ema21": [...],
  "macd_line"/"macd_signal"/"macd_hist": [...],
  "golden_cross": {date, index, bars_since, fresh, ema5, ema21} | null,
  "last_dead_cross": {date, index} | null,
  "last": {...latest values...},
  "ema5_above_ema21": bool
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

from . import technicals as ta


def _week_key(d: datetime) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso[0], iso[1])


def _resample_weekly(candles: list[dict]) -> list[dict]:
    """Group daily candles into weekly OHLCV bars (first open, last close)."""
    weeks: dict[tuple[int, int], list[dict]] = {}
    for c in candles:
        try:
            d = datetime.strptime(str(c["date"]), "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        weeks.setdefault(_week_key(d), []).append(c)

    out: list[dict] = []
    for key in sorted(weeks):
        rows = weeks[key]
        out.append(
            {
                "date": rows[0]["date"],
                "open": float(rows[0]["open"]),
                "high": max(float(r["high"]) for r in rows),
                "low": min(float(r["low"]) for r in rows),
                "close": float(rows[-1]["close"]),
                "volume": float(sum(float(r.get("volume") or 0.0) for r in rows)),
            }
        )
    return out


def _ema_skipnan(values: np.ndarray, period: int) -> np.ndarray:
    """EMA that skips a leading NaN run (e.g. MACD line before slow EMA warms up)."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    start = 0
    while start < n and not np.isfinite(values[start]):
        start += 1
    if n - start < period:
        return out
    alpha = 2.0 / (period + 1.0)
    prev = float(np.mean(values[start:start + period]))
    out[start + period - 1] = prev
    for i in range(start + period, n):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _crosses(a: np.ndarray, b: np.ndarray) -> list[int]:
    """Indices where series a crosses above series b (both must be finite)."""
    out: list[int] = []
    for i in range(1, len(a)):
        if (
            np.isfinite(a[i - 1]) and np.isfinite(b[i - 1])
            and np.isfinite(a[i]) and np.isfinite(b[i])
            and a[i - 1] <= b[i - 1] and a[i] > b[i]
        ):
            out.append(i)
    return out


def _ser(v: np.ndarray) -> list:
    return [None if not np.isfinite(x) else round(float(x), 2) for x in v]


def build_weekly_chart(candles: list[dict], max_bars: int = 120) -> Optional[dict]:
    """Weekly chart payload, or None when there isn't enough history."""
    weekly = _resample_weekly(candles)
    if len(weekly) < 30:  # need enough bars for BB(20) + MACD to be meaningful
        return None
    weekly = weekly[-max_bars:]
    n = len(weekly)

    close = np.asarray([c["close"] for c in weekly], dtype=float)
    bb_mid, bb_upper, bb_lower = ta.bollinger(close, 20, 2.0)
    ema5 = ta.ema(close, 5)
    ema21 = ta.ema(close, 21)
    macd_line = ta.ema(close, 12) - ta.ema(close, 26)
    macd_signal = _ema_skipnan(macd_line, 9)
    macd_hist = macd_line - macd_signal

    gc = _crosses(ema5, ema21)
    golden = None
    if gc:
        idx = gc[-1]
        fresh = (n - 1 - idx) <= 2  # cross happened on the last bar or up to 2 weeks ago
        golden = {
            "date": weekly[idx]["date"],
            "index": idx,
            "bars_since": n - 1 - idx,
            "fresh": fresh,
            "ema5": round(float(ema5[idx]), 2),
            "ema21": round(float(ema21[idx]), 2),
        }

    dc = _crosses(ema21, ema5)  # dead cross = EMA21 crosses above EMA5
    last_dead = None
    if dc:
        idx = dc[-1]
        last_dead = {"date": weekly[idx]["date"], "index": idx}

    def _v(arr: np.ndarray) -> Optional[float]:
        v = float(arr[-1])
        return round(v, 2) if np.isfinite(v) else None

    return {
        "frame": "1W",
        "candles": weekly,
        "bb_upper": _ser(bb_upper),
        "bb_mid": _ser(bb_mid),
        "bb_lower": _ser(bb_lower),
        "ema5": _ser(ema5),
        "ema21": _ser(ema21),
        "macd_line": _ser(macd_line),
        "macd_signal": _ser(macd_signal),
        "macd_hist": _ser(macd_hist),
        "golden_cross": golden,
        "last_dead_cross": last_dead,
        "last": {
            "date": weekly[-1]["date"],
            "close": round(float(close[-1]), 2),
            "ema5": _v(ema5),
            "ema21": _v(ema21),
            "bb_upper": _v(bb_upper),
            "bb_mid": _v(bb_mid),
            "bb_lower": _v(bb_lower),
            "macd": _v(macd_line),
            "macd_signal": _v(macd_signal),
            "macd_hist": _v(macd_hist),
        },
        "ema5_above_ema21": bool(
            np.isfinite(ema5[-1]) and np.isfinite(ema21[-1]) and ema5[-1] > ema21[-1]
        ),
    }