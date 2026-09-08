"""Backtesting engine for the Layer A swing-pullback strategy.

History comes from yfinance by default (0 arjum quota). Layer A rules are applied
causally bar-by-bar: entry on the next bar's open, exits at TP1 (50%) / TP2 / stop
/ structural lower-band break / max holding days. Trade P&L is computed on a
cost-basis (fees included on every leg).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from . import technicals as ta
from .arjum import ArjumClient
from .models import BacktestParams
from .scanner import _fetch_history

logger = logging.getLogger(__name__)


async def backtest(
    code: str,
    params: BacktestParams,
    client: Optional[ArjumClient] = None,
) -> dict:
    ticker = code.upper().removesuffix(".JK")
    from datetime import date, timedelta

    start_date = (date.today() - timedelta(days=365 * params.history_years)).isoformat()
    candles, history_error = await _fetch_history(
        ticker, params, client, period="1y", start_date=start_date
    )
    if not candles:
        return {"ticker": ticker, "error": history_error or f"Tidak ada data history untuk {ticker}"}

    close = np.asarray([c["close"] for c in candles], dtype=float)
    high = np.asarray([c["high"] for c in candles], dtype=float)
    low = np.asarray([c["low"] for c in candles], dtype=float)
    open_ = np.asarray([c["open"] for c in candles], dtype=float)
    volume = np.asarray([c["volume"] for c in candles], dtype=float)
    dates = [c["date"] for c in candles]
    n = len(close)

    ema20 = ta.ema(close, params.ema_period)
    sma50 = ta.sma(close, params.sma_period)
    ema5 = ta.ema(close, 5)
    _, _, lower = ta.bollinger(close, params.bb_period, params.bb_std)
    rsi14 = ta.rsi(close, 14)
    liq = _rolling_avg_value(close, volume, 20)
    pull = _rolling_pullback(close, high, 20)
    atr14 = ta.atr(high, low, close, 14)
    touch_any = ta.close_near_lower_band(close, lower, params.touch_window_days)

    def signal_at(i: int) -> bool:
        # Mirror of the live Layer A gate (app/scanner.py:_layer_a): the touch
        # window counts when a low touched the band recently OR the current bar is
        # near the band within touch_tolerance_pct; band_gap_max_pct caps how far
        # the CLOSE may sit above the lower band (the per-method knob).
        if i < max(params.min_history_days, params.sma_period, params.bb_period) - 1:
            return False
        if np.isnan(ema20[i]) or np.isnan(sma50[i]) or np.isnan(lower[i]) or np.isnan(rsi14[i]):
            return False
        near_band = min(close[i], low[i]) <= lower[i] * (1.0 + params.touch_tolerance_pct / 100.0)
        touch_ok = bool(touch_any[i] or near_band)
        band_gap_ok = (
            params.band_gap_max_pct <= 0
            or lower[i] <= 0
            or (close[i] - lower[i]) / lower[i] * 100.0 <= params.band_gap_max_pct
        )
        rsi_ok = (params.rsi_max <= 0 or rsi14[i] < params.rsi_max) and rsi14[i] <= 70
        confirmation_ok = True
        if params.require_green_day:
            confirmation_ok = confirmation_ok and close[i] > open_[i]
        if params.require_close_above_ema5:
            confirmation_ok = confirmation_ok and np.isfinite(ema5[i]) and close[i] > ema5[i]
        return bool(
            close[i] > ema20[i] > sma50[i]
            and near_band
            and touch_ok
            and band_gap_ok
            and liq[i] > params.min_liquidity_idr
            and close[i] >= params.min_price
            and (params.max_price is None or close[i] <= params.max_price)
            and rsi_ok
            and (params.pullback_pct <= 0 or pull[i] >= params.pullback_pct)
            and confirmation_ok
        )

    # ---- simulation state ----
    cash = params.start_capital
    shares = 0          # currently held
    entry_shares = 0    # total shares bought at entry (for reporting)
    cost_basis = 0.0    # total cost (fees incl.) of the open position
    entry_price = 0.0
    entry_date = ""
    tp1_price = tp2_price = stop = 0.0
    tp1_done = False
    hold_days = 0
    leg_proceeds = 0.0  # proceeds already realized on the TP1 partial leg
    trail_peak = 0.0    # highest close since entry (for trailing stop)

    trades: list[dict] = []
    curve: list[list] = []
    peak = params.start_capital
    max_dd = 0.0
    gross_win = 0.0
    gross_loss = 0.0

    def buy(shares_: int, price: float) -> None:
        nonlocal cash, shares, cost_basis
        cost = shares_ * price * (1.0 + params.fee_pct / 100.0)
        cash -= cost
        shares += shares_
        cost_basis += cost

    def sell(shares_: int, price: float) -> float:
        nonlocal cash, shares
        proceeds = shares_ * price * (1.0 - params.fee_pct / 100.0)
        cash += proceeds
        shares -= shares_
        return proceeds

    def close_trade(exit_date: str, exit_price: float,                reason: str, sold_shares: int, proceeds: float) -> None:
        nonlocal gross_win, gross_loss
        ret = (proceeds - cost_basis) / cost_basis * 100.0 if cost_basis > 0 else 0.0
        trades.append(
            {
                "entry_date": entry_date,
                "entry_price": round(entry_price, 0),
                "exit_date": exit_date,
                "exit_price": round(exit_price, 0),
                "reason": reason,
                "return_pct": round(ret, 2),
                "lots": entry_shares // 100,
                "hold_days": hold_days,
            }
        )
        if ret > 0:
            gross_win += ret
        else:
            gross_loss += abs(ret)

    for i in range(n):
        # ---------- exits ----------
        if shares > 0:
            hold_days += 1
            trail_peak = max(trail_peak, float(close[i]))

            if not tp1_done and high[i] >= tp1_price:
                half = shares // 2
                if half > 0:
                    leg_proceeds += sell(half, tp1_price)
                    tp1_done = True

            exit_price: Optional[float] = None
            reason = ""
            if tp1_done and high[i] >= tp2_price:
                exit_price, reason = tp2_price, "TP2"
            elif low[i] <= stop:
                exit_price, reason = stop, "STOP"
            elif params.trail_pct > 0 and trail_peak > 0 and close[i] <= trail_peak * (1.0 - params.trail_pct / 100.0):
                exit_price, reason = close[i], "TRAIL"
            elif close[i] < (ema20[i] if params.exit_on_ema20_break else lower[i]):
                exit_price, reason = close[i], "STRUCTURAL"
            elif hold_days >= params.max_hold_days:
                exit_price, reason = close[i], "TIMEOUT"

            if exit_price is not None and shares > 0:
                proceeds = sell(shares, exit_price)
                close_trade(dates[i], exit_price, reason, shares, leg_proceeds + proceeds)
                shares = 0
                cost_basis = 0.0
                leg_proceeds = 0.0

        # ---------- entry ----------
        if shares == 0 and i + 1 < n and signal_at(i):
            open_next = float(close[i + 1])
            entry_price = open_next * (1.0 + params.slippage_pct / 100.0)
            a = float(atr14[i])
            if np.isnan(a) or a <= 0:
                a = entry_price * 0.02
            stop = max(entry_price * (1.0 - params.sl_pct / 100.0), entry_price - params.atr_stop_mult * a)
            tp1_price = entry_price * (1.0 + params.tp1_pct / 100.0)
            tp2_price = entry_price * (1.0 + params.tp2_pct / 100.0)
            risk_per_share = entry_price - stop
            if risk_per_share <= 0:
                continue
            risk_budget = params.start_capital * params.risk_per_trade_pct / 100.0
            lots = int(risk_budget / risk_per_share) // 100
            lots = max(0, min(lots, int(cash / (entry_price * 100.0))))
            if lots == 0:
                continue
            buy(lots * 100, entry_price)
            entry_shares = lots * 100
            entry_date = dates[i + 1]
            tp1_done = False
            hold_days = 0
            leg_proceeds = 0.0

        # ---------- equity curve ----------
        equity = cash + shares * float(close[i])
        curve.append([dates[i], round(equity, 0)])
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)

    # liquidate anything left at last close (open position)
    if shares > 0:
        proceeds = sell(shares, float(close[-1]))
        close_trade(dates[-1], float(close[-1]), "OPEN", shares, leg_proceeds + proceeds)
        shares = 0
        cost_basis = 0.0
        leg_proceeds = 0.0

    # ---------- metrics ----------
    n_trades = len(trades)
    wins = sum(1 for t in trades if t["return_pct"] > 0)
    rets = [t["return_pct"] for t in trades]
    final_equity = cash
    return {
        "ticker": ticker,
        "metrics": {
            "n_trades": n_trades,
            "win_rate_pct": round(wins / n_trades * 100.0, 1) if n_trades else None,
            "avg_return_pct": round(sum(rets) / len(rets), 2) if rets else None,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else (None if not rets else round(gross_win, 2)),
            "max_drawdown_pct": round(max_dd, 2),
            "start_capital": round(params.start_capital, 0),
            "final_equity": round(final_equity, 0),
            "total_return_pct": round((final_equity - params.start_capital) / params.start_capital * 100.0, 2),
            "avg_hold_days": round(sum(t["hold_days"] for t in trades) / n_trades, 1) if n_trades else None,
        },
        "trades": trades,
        "equity_curve": curve,
        "strategy_params": {
            "ema_period": params.ema_period,
            "sma_period": params.sma_period,
            "bb_period": params.bb_period,
            "bb_std": params.bb_std,
            "touch_tolerance_pct": params.touch_tolerance_pct,
            "band_gap_max_pct": params.band_gap_max_pct,
            "rsi_max": params.rsi_max,
            "pullback_pct": params.pullback_pct,
            "min_liquidity_idr": params.min_liquidity_idr,
            "min_price": params.min_price,
            "tp1_pct": params.tp1_pct,
            "tp2_pct": params.tp2_pct,
            "sl_pct": params.sl_pct,
            "atr_stop_mult": params.atr_stop_mult,
            "max_hold_days": params.max_hold_days,
            "fee_pct": params.fee_pct,
            "slippage_pct": params.slippage_pct,
            "risk_per_trade_pct": params.risk_per_trade_pct,
        },
        "n_bars": n,
        "start_date": dates[0],
        "end_date": dates[-1],
    }


def _rolling_avg_value(close: np.ndarray, volume: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    for i in range(window - 1, len(close)):
        out[i] = float(np.mean(close[i - window + 1: i + 1] * volume[i - window + 1: i + 1]))
    return out


def _rolling_pullback(close: np.ndarray, high: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    for i in range(window - 1, len(close)):
        peak = float(np.max(high[i - window + 1: i + 1]))
        if peak > 0:
            out[i] = (peak - close[i]) / peak * 100.0
    return out