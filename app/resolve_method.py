"""Named Layer A method loader for the live API default path.

Keeps the live ``/scan`` defaults consistent with the same method set used by
``scripts/scan_all_codes_variants.py`` instead of maintaining two separate
copies of the philosophy.

The only supported resolution right now is the ``mapped`` universe + yfinance
pipeline, because the production scan is currently the mapped-path the user
cared about.
"""
from __future__ import annotations

from typing import Optional

from app.models import ScanParams

SUPPORTED_METHODS = {
    "strict_strong_buy": {
        "rsi_max": 55.0,
        "pullback_pct": 4.0,
        "band_gap_max_pct": 2.0,
        "min_price": 100.0,
        "min_liquidity_idr": 5_000_000_000.0,
        "touch_tolerance_pct": 1.0,
        "touch_window_days": 5,
        "description": "Tight conviction-only output: uptrend + liquid + close within 2% of lower band + RSI <= 55 + pullback >= 4%.",
    },
    "buy_quality_tighter": {
        "rsi_max": 60.0,
        "pullback_pct": 3.0,
        "band_gap_max_pct": 3.0,
        "min_price": 100.0,
        "min_liquidity_idr": 5_000_000_000.0,
        "touch_tolerance_pct": 1.0,
        "touch_window_days": 5,
        "description": "Quality buy candidates: uptrend + liquid + RSI <= 60 + pullback >= 3% + band gap <= 3%.",
    },
    "band_proximity_main": {
        "rsi_max": 65.0,
        "pullback_pct": 2.0,
        "band_gap_max_pct": 3.0,
        "min_price": 100.0,
        "min_liquidity_idr": 5_000_000_000.0,
        "touch_tolerance_pct": 1.0,
        "touch_window_days": 5,
        "description": "Main method: lower-band proximity is the central swing idea, with RSI <= 65 and pullback >= 2%.",
    },
    "wide_candidate_pool": {
        "rsi_max": 70.0,
        "pullback_pct": 1.0,
        "band_gap_max_pct": 4.0,
        "min_price": 50.0,
        "min_liquidity_idr": 1_000_000_000.0,
        "touch_tolerance_pct": 1.0,
        "touch_window_days": 5,
        "description": "Broad candidate pool: lower-priced names allowed, lower liquidity floor, RSI <= 70, pullback >= 1%, band gap <= 4%.",
    },
}


def default_method_params(*, method: Optional[str] = None) -> tuple[Optional[ScanParams], Optional[str]]:
    """Return a ScanParams preset for a named method, or None if unknown/unset.

    The returned params deliberately keep the backtest-backed blueprint defaults
    (TP/SL/hold) untouched — this is only about the technical screen philosophy.
    """
    if not method:
        return None, None

    m = SUPPORTED_METHODS.get(method)
    if not m:
        return None, f"tidak dikenal: {method}"

    return ScanParams(
        data_source="yfinance",
        lookback_days=15,
        top_n_brokers=3,
        price_anchor_pct=3.0,
        min_price=m["min_price"],
        max_price=None,
        min_history_days=60,
        ema_period=20,
        sma_period=50,
        bb_period=20,
        bb_std=2.0,
        touch_tolerance_pct=m["touch_tolerance_pct"],
        touch_window_days=m["touch_window_days"],
        rsi_max=m["rsi_max"],
        pullback_pct=m["pullback_pct"],
        min_liquidity_idr=m["min_liquidity_idr"],
        retail_brokers=["YP", "CC", "NI"],
        retail_share_min=0.5,
        tp1_pct=5.0,
        tp2_pct=10.0,
        sl_pct=5.0,
        atr_stop_mult=2.0,
        risk_per_trade_pct=2.0,
        portfolio_idr=100_000_000.0,
        universe="mapped",
        sector=None,
        min_market_cap_idr=3_000_000_000_000.0,
        max_tickers=300,
        include_seasonality=False,
        include_news=False,
    ), m["description"]


def list_methods() -> dict[str, dict]:
    return {
        name: {
            "description": m["description"],
            "params": {
                "rsi_max": m["rsi_max"],
                "pullback_pct": m["pullback_pct"],
                "band_gap_max_pct": m["band_gap_max_pct"],
                "min_price": m["min_price"],
                "min_liquidity_idr": m["min_liquidity_idr"],
                "touch_tolerance_pct": m["touch_tolerance_pct"],
                "touch_window_days": m["touch_window_days"],
            },
        }
        for name, m in SUPPORTED_METHODS.items()
    }


def is_valid_method(name: Optional[str]) -> bool:
    return bool(name) and name in SUPPORTED_METHODS
