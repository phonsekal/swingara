"""Unit tests for app.technicals."""
import numpy as np

from app import technicals as ta


def _closes(n: int = 120) -> np.ndarray:
    return np.arange(100.0, 100.0 + n, 1.0)


def test_sma():
    x = _closes(10)
    out = ta.sma(x, 5)
    assert np.isnan(out[3])
    assert out[4] == 102.0  # mean of 100..104
    assert out[9] == 107.0  # mean of 105..109


def test_ema_uptrend_above_sma():
    x = _closes(120)
    e = ta.ema(x, 20)
    s = ta.sma(x, 50)
    assert e[-1] > s[-1]
    assert e[-1] < x[-1]  # lagging behind price in an uptrend


def test_bollinger_order():
    x = _closes(120)
    mid, upper, lower = ta.bollinger(x, 20, 2.0)
    assert mid[-1] < upper[-1]
    assert lower[-1] < mid[-1]
    assert upper[-1] - mid[-1] == mid[-1] - lower[-1]  # symmetric bands


def test_atr_positive():
    high = np.full(60, 110.0)
    low = np.full(60, 90.0)
    close = np.full(60, 100.0)
    a = ta.atr(high, low, close, 14)
    assert a[13] == 20.0
    assert np.allclose(a[13:], 20.0)


def test_rsi_bounds():
    rising = np.arange(1.0, 60.0, 1.0)
    falling = np.arange(60.0, 1.0, -1.0)
    assert ta.rsi(rising, 14)[-1] > 90
    assert ta.rsi(falling, 14)[-1] < 10


def test_vwap_and_avg_value():
    close = np.array([10.0, 20.0, 30.0])
    volume = np.array([100.0, 100.0, 100.0])
    assert ta.vwap(close, volume, 3) == 20.0
    assert ta.avg_transaction_value(close, volume, 2) == 25.0 * 100.0


def test_pullback_pct():
    close = np.array([10.0, 20.0, 15.0])
    high = np.array([12.0, 22.0, 16.0])
    assert abs(ta.pullback_pct(close, high, 3) - (22.0 - 15.0) / 22.0 * 100.0) < 1e-9