"""Technical indicator layer (Layer A). Pure numpy — no pandas dependency."""
from __future__ import annotations

import numpy as np


def sma(values: np.ndarray, period: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < period or period <= 0:
        return out
    cum = np.cumsum(np.insert(values, 0, 0.0))
    out[period - 1:] = (cum[period:] - cum[:-period]) / period
    return out


def ema(values: np.ndarray, period: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < period or period <= 0:
        return out
    alpha = 2.0 / (period + 1.0)
    prev = float(np.mean(values[:period]))
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def bollinger(
    close: np.ndarray, period: int = 20, num_std: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (middle, upper, lower) band series."""
    close = np.asarray(close, dtype=float)
    n = len(close)
    mid = sma(close, period)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = close[i - period + 1: i + 1]
        std = float(np.std(window))  # population std (ddof=0), matches TradingView
        upper[i] = mid[i] + num_std * std
        lower[i] = mid[i] - num_std * std
    return mid, upper, lower


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(close)
    out = np.full(n, np.nan)
    if n < period or period <= 0:
        return out
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    prev = float(np.mean(tr[:period]))
    out[period - 1] = prev
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI."""
    close = np.asarray(close, dtype=float)
    n = len(close)
    out = np.full(n, np.nan)
    if n <= period or period <= 0:
        return out
    gains = np.maximum(np.diff(close), 0.0)
    losses = np.maximum(-np.diff(close), 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    def _value(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0
        rs = ag / al
        return 100.0 - 100.0 / (1.0 + rs)

    out[period] = _value(avg_gain, avg_loss)
    for i in range(period, n - 1):
        g = float(gains[i])
        l = float(losses[i])
        if not (np.isfinite(g) and np.isfinite(l)):
            out[i + 1] = np.nan
            continue
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        out[i + 1] = _value(avg_gain, avg_loss)
    return out


def vwap(close: np.ndarray, volume: np.ndarray, window: int) -> float:
    close = np.asarray(close, dtype=float)
    volume = np.asarray(volume, dtype=float)
    n = len(close)
    if n < window or window <= 0:
        return float("nan")
    vol = volume[-window:]
    total = float(np.sum(vol))
    if total <= 0:
        return float("nan")
    return float(np.sum(close[-window:] * vol) / total)


def avg_transaction_value(close: np.ndarray, volume: np.ndarray, window: int = 20) -> float:
    close = np.asarray(close, dtype=float)
    volume = np.asarray(volume, dtype=float)
    n = len(close)
    if n < window or window <= 0:
        return float("nan")
    return float(np.mean(close[-window:] * volume[-window:]))


def pullback_pct(close: np.ndarray, high: np.ndarray, window: int = 20) -> float:
    """How far the current close has retraced from the window's highest high, in %."""
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    n = len(close)
    if n < 2 or window <= 0:
        return float("nan")
    peak = float(np.max(high[-window:]))
    if peak <= 0:
        return float("nan")
    return (peak - close[-1]) / peak * 100.0


def close_near_lower_band(close: np.ndarray, lower: np.ndarray, window: int) -> np.ndarray:
    """For each bar i, True if any of close[-window:i+1] is near/through lower band.

    Used as a multi-bar confirmation: the pullback must have touched (or come very
    close to) the lower Bollinger band at some point in the recent window, not only
    on the single signal bar.
    """
    close = np.asarray(close, dtype=float)
    lower = np.asarray(lower, dtype=float)
    n = len(close)
    out = np.full(n, False)
    if n < window or window <= 0:
        return out
    for i in range(window - 1, n):
        segment_lower = lower[i - window + 1: i + 1]
        segment_close = close[i - window + 1: i + 1]
        if np.any(np.isnan(segment_lower)):
            continue
        peak_low = float(np.min(segment_close))
        band_low = float(np.min(segment_lower))
        if peak_low <= band_low:
            out[i] = True
    return out