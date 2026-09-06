"""Trading blueprint builder (Section 4 of the spec)."""
from __future__ import annotations

from .models import ScanParams


def build_plan(
    close: float,
    lower_band: float,
    atr_val: float,
    params: ScanParams,
) -> dict:
    """Entry range, take profits, stop loss and suggested lot size."""
    entry_high = close
    entry_low = min(close, lower_band)

    tp1 = round(entry_high * (1.0 + params.tp1_pct / 100.0), 0)
    tp2 = round(entry_high * (1.0 + params.tp2_pct / 100.0), 0)
    sl_fixed = entry_high * (1.0 - params.sl_pct / 100.0)
    sl_atr = entry_high - params.atr_stop_mult * atr_val
    stop_loss = max(sl_fixed, sl_atr)  # tighter of the two stops

    risk_per_share = entry_high - stop_loss
    risk_budget = params.portfolio_idr * params.risk_per_trade_pct / 100.0
    if risk_per_share > 0:
        shares = int(risk_budget / risk_per_share)
    else:
        shares = 0
    lots = max(0, shares // 100)
    max_lots_by_capital = int(params.portfolio_idr / (entry_high * 100.0)) if entry_high > 0 else 0
    lots = min(lots, max_lots_by_capital)

    return {
        "entry_zone": {"from": round(entry_low, 0), "to": round(entry_high, 0)},
        "tp1_pct": params.tp1_pct,
        "tp1_price": round(tp1, 0),
        "tp1_note": f"Sell 50% of position at +{params.tp1_pct:g}%",
        "tp2_pct": params.tp2_pct,
        "tp2_price": round(tp2, 0),
        "tp2_note": f"Full liquidation at +{params.tp2_pct:g}%",
        "sl_pct": params.sl_pct,
        "sl_atr_mult": params.atr_stop_mult,
        "sl_fixed_price": round(sl_fixed, 0),
        "sl_atr_price": round(sl_atr, 0),
        "stop_loss": round(stop_loss, 0),
        "structural_exit_note": "Exit if daily close breaks the Lower Bollinger Band",
        "suggested_lots": lots,
        "suggested_shares": lots * 100,
        "risk_per_share": round(risk_per_share, 0),
        "risk_budget_idr": round(risk_budget, 0),
    }