"""Triple-layer swing scanner: Layer A (technicals) + Layer B (bandarmology,
optional broker filter) + Layer C (anti-retail distribution audit)."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np

from . import technicals as ta
from .arjum import ArjumClient, ArjumAuthError, ArjumError
from .explain import explain_verdict
from .extras import fetch_corp_actions, fetch_news
from .models import ScanParams, StockVerdict
from .plan import build_plan
from .seasonality import monthly_seasonality
from .yf_lock import yf_lock

logger = logging.getLogger(__name__)

# Bars of history to request: enough for EMA50/BB(20) stability + lookback anchor
HISTORY_BARS = 200


# --------------------------------------------------------------------------- data

def _parse_candles(raw: dict) -> list[dict]:
    return raw.get("candles") or []


async def _history_from_yfinance(
    code: str,
    bars: int = 0,
    period: str = "1y",
    start_date: Optional[str] = None,
) -> list[dict]:
    """yfinance data source (0 arjum quota).

    `period` = Yahoo period ("1y"/"max"); alternatively pass `start_date`
    (YYYY-MM-DD) for a deterministic multi-year window. Returns the FULL series
    (callers slice as needed) so seasonality can use the same download.
    """
    try:
        import yfinance as yf  # optional dependency
    except ImportError as exc:  # pragma: no cover - env dependent
        raise ArjumError("yfinance tidak terpasang. Install dengan: pip install yfinance") from exc

    kwargs = {"interval": "1d", "auto_adjust": False, "progress": False}
    if start_date:
        kwargs["start"] = start_date
    else:
        kwargs["period"] = period

    def _download():
        # serialize: yfinance is not thread-safe (shared cache -> crossed data)
        with yf_lock:
            return yf.download(f"{code}.JK", **kwargs)

    df = await asyncio.to_thread(_download)
    if df is None or df.empty:
        raise ArjumError(f"yfinance tidak mengembalikan data untuk {code}.JK")

    def _col(key: str) -> np.ndarray:
        """Find a column by name, tolerant of MultiIndex / duplicate names."""
        for col in df.columns:
            name = col[0] if isinstance(col, tuple) else str(col)
            name = str(name).lower().split(",")[0].strip()
            if name == key.lower():
                return df[col].to_numpy(dtype=float)
        raise ArjumError(f"yfinance tidak mengembalikan kolom {key} untuk {code}.JK")

    opens, highs, lows, closes = (_col(k) for k in ("Open", "High", "Low", "Close"))
    volumes = _col("Volume")
    volumes = np.nan_to_num(volumes)
    n = len(closes)
    start = max(0, n - bars) if bars else 0
    rows: list[dict] = []
    for i in range(start, n):
        rows.append(
            {
                "date": df.index[i].strftime("%Y-%m-%d"),
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "volume": float(volumes[i]),
            }
        )
    if not rows:
        raise ArjumError(f"yfinance tidak mengembalikan data untuk {code}.JK")
    return rows


async def _fetch_history(
    code: str,
    params: ScanParams,
    client: Optional[ArjumClient],
    period: str = "1y",
    start_date: Optional[str] = None,
) -> tuple[list[dict], Optional[str]]:
    """History via arjum (primary) with automatic yfinance fallback.

    `period` is the Yahoo download period ("1y" fast / "max" for seasonality);
    `start_date` overrides it with a deterministic multi-year window.
    """
    error: Optional[str] = None
    candles: list[dict] = []

    # multi-year downloads return the full series (bars=0); otherwise keep last N bars
    bars = 0 if start_date else HISTORY_BARS

    if params.data_source == "arjum" and client is not None:
        try:
            candles = _parse_candles(await client.history(code, limit=HISTORY_BARS))
        except ArjumAuthError as exc:
            error = str(exc)
        except ArjumError as exc:
            error = str(exc)
    if not candles and params.data_source == "yfinance":
        try:
            candles = await _history_from_yfinance(code, bars, period, start_date)
        except ArjumError as exc:
            error = str(exc)
    # no arjum client at all (e.g. no API key configured) -> straight to yfinance
    if not candles and error is None:
        try:
            candles = await _history_from_yfinance(code, bars, period, start_date)
        except ArjumError as exc:
            error = str(exc)
    # arjum failed (auth/network) -> transparent fallback to yfinance if usable
    if not candles and error and params.data_source == "arjum":
        try:
            candles = await _history_from_yfinance(code, bars, period, start_date)
            error = None
        except ArjumError:
            pass  # keep original error

    return candles, error


# ----------------------------------------------------------------------- layers

def _layer_a(candles: list[dict], params: ScanParams) -> tuple[bool, dict]:
    close = np.asarray([c["close"] for c in candles], dtype=float)
    high = np.asarray([c["high"] for c in candles], dtype=float)
    low = np.asarray([c["low"] for c in candles], dtype=float)
    volume = np.asarray([c["volume"] for c in candles], dtype=float)
    n = len(candles)

    ema20 = ta.ema(close, params.ema_period)
    sma50 = ta.sma(close, params.sma_period)
    _, _, lower = ta.bollinger(close, params.bb_period, params.bb_std)
    atr14 = ta.atr(high, low, close, 14)
    rsi14 = ta.rsi(close, 14)
    touch_any = ta.close_near_lower_band(close, lower, params.touch_window_days)

    last = n - 1
    price = float(close[last])
    e20 = float(ema20[last])
    s50 = float(sma50[last])
    lb = float(lower[last])
    a = float(atr14[last])
    r = float(rsi14[last])

    checks: dict[str, bool] = {}
    checks["uptrend"] = bool(price > e20 > s50)
    checks["discount_zone"] = bool(
        min(price, float(low[last]))
        <= lb * (1.0 + params.touch_tolerance_pct / 100.0)
    )
    checks["touch_window"] = bool(touch_any[last])
    liq = ta.avg_transaction_value(close, volume, 20)
    checks["liquidity"] = bool(liq > params.min_liquidity_idr)
    checks["min_price"] = bool(price >= params.min_price)
    checks["max_price"] = bool(
        params.max_price is None or price <= params.max_price
    )
    checks["min_history"] = bool(n >= params.min_history_days)
    checks["rsi_ok"] = bool(params.rsi_max <= 0 or r < params.rsi_max)
    pull = ta.pullback_pct(close, high, 20)
    checks["pullback"] = bool(params.pullback_pct <= 0 or pull >= params.pullback_pct)

    # --- Lower-band proximity method cap ---
    # This turns the old single combined gate into the named-method philosophy
    # used by scripts/scan_all_codes_variants.py **only when the caller opts
    # into band_gap_max_pct > 0**. The live default scan sets this when a
    # named method is used; the generic API still treats 0 as "no extra cap".
    band_gap = None
    if params.band_gap_max_pct > 0 and lb and lb > 0:
        band_gap = (price - lb) / lb * 100.0
        checks["band_gap_ok"] = bool(band_gap <= params.band_gap_max_pct)
    else:
        checks["band_gap_ok"] = True
        band_gap = band_gap

    passed = all(checks.values())
    return passed, {
        "passed": passed,
        "checks": checks,
        "close": round(price, 0),
        "ema_period": params.ema_period,
        "sma_period": params.sma_period,
        "ema20": round(e20, 0) if e20 == e20 else None,
        "sma50": round(s50, 0) if s50 == s50 else None,
        "bb_period": params.bb_period,
        "lower_band": round(lb, 0) if lb == lb else None,
        "atr14": round(a, 0) if a == a else None,
        "rsi14": round(r, 1) if r == r else None,
        "avg_20d_value_idr": round(liq, 0) if liq == liq else None,
        "pullback_from_20d_high_pct": round(pull, 2) if pull == pull else None,
        "band_gap_pct": round(band_gap, 2) if band_gap is not None and band_gap == band_gap else None,
        "band_gap_max_pct": params.band_gap_max_pct if params.band_gap_max_pct > 0 else None,
    }


def _layer_bc(
    raw: dict, candles: list[dict], params: ScanParams
) -> tuple[dict, dict]:
    """Compute Layer B (institutional/SS accumulation) and Layer C (retail dump)."""
    brokers = raw.get("brokers") or []
    b_detail: dict = {"status": "fail", "details": {}}
    c_detail: dict = {"status": "fail", "details": {}}

    if not brokers:
        b_detail["details"] = {"reason": "broker_summary kosong"}
        return b_detail, c_detail

    rows = [
        {
            "broker_code": str(b.get("broker_code", "")).upper(),
            "broker_name": b.get("broker_name", ""),
            "bval": float(b.get("bval") or 0.0),
            "sval": float(b.get("sval") or 0.0),
            "nval": float(b.get("nval") or 0.0),
            "nvol": float(b.get("nvol") or 0.0),
        }
        for b in brokers
    ]

    # Rank buyers (positive net) and sellers (most negative net)
    by_nval = sorted(rows, key=lambda r: r["nval"], reverse=True)
    top_buyers = [r for r in by_nval if r["nval"] > 0][: params.top_n_brokers]
    top_sellers = sorted(rows, key=lambda r: r["nval"])[: params.top_n_brokers]

    retail_codes = {c.upper() for c in params.retail_brokers}
    requested = {c.upper() for c in params.brokers} if params.brokers else None

    # ---- Layer B: broker match ----
    if requested is not None:
        # strict mode: one of the pinned brokers must be a top net buyer
        matched = [r for r in top_buyers if r["broker_code"] in requested]
        match_rule = f"requires one of {sorted(requested)} in Top {params.top_n_brokers} net buyers"
    else:
        # loose mode: any non-retail (institutional) broker in top buyers
        matched = [r for r in top_buyers if r["broker_code"] not in retail_codes]
        match_rule = (
            f"any non-retail broker in Top {params.top_n_brokers} net buyers "
            f"(retail excluded: {sorted(retail_codes)})"
        )

    # ---- Anchor / chase protection ----
    close_arr = np.asarray([c["close"] for c in candles], dtype=float)
    vol_arr = np.asarray([c["volume"] for c in candles], dtype=float)
    lookback = max(2, min(params.lookback_days, len(close_arr)))
    if params.anchor_mode == "avg_close":
        anchor = float(np.mean(close_arr[-lookback:]))
    else:
        anchor = ta.vwap(close_arr, vol_arr, lookback)
    price = float(close_arr[-1])
    anchor_ok = bool(price <= anchor * (1.0 + params.price_anchor_pct / 100.0))

    b_pass = bool(matched) and anchor_ok
    b_detail = {
        "status": "pass" if b_pass else "fail",
        "details": {
            "match_rule": match_rule,
            "top_buyers": top_buyers[: params.top_n_brokers],
            "matched_brokers": matched,
            "anchor_mode": params.anchor_mode,
            "lookback_days": lookback,
            "buy_avg_anchor": round(anchor, 0) if anchor == anchor else None,
            "price": round(price, 0),
            "anchor_buffer_pct": round((price / anchor - 1.0) * 100.0, 2) if anchor else None,
            "price_anchor_ok": anchor_ok,
            "price_anchor_max": round(anchor * (1.0 + params.price_anchor_pct / 100.0), 0) if anchor == anchor else None,
        },
    }

    # ---- Layer C: retail distribution audit ----
    neg_sellers = [r for r in top_sellers if r["nval"] < 0]
    total_neg = sum(r["nval"] for r in neg_sellers)
    retail_sellers = [r for r in neg_sellers if r["broker_code"] in retail_codes]
    retail_neg = sum(r["nval"] for r in retail_sellers)
    share = (retail_neg / total_neg) if total_neg < 0 else 0.0
    c_pass = bool(retail_sellers) and share >= params.retail_share_min
    c_detail = {
        "status": "pass" if c_pass else "fail",
        "details": {
            "top_sellers": neg_sellers[: params.top_n_brokers],
            "retail_brokers": sorted(retail_codes),
            "retail_sellers": retail_sellers,
            "retail_share_of_net_sell": round(share, 3),
            "retail_share_min": params.retail_share_min,
        },
    }
    return b_detail, c_detail


# ----------------------------------------------------------------------- verdict

def _verdict(a_pass: bool, b_status: str, c_status: str, b_fail_reason: Optional[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not a_pass:
        return "REJECTED", ["Layer A (technical) gagal"]
    if b_status == "unavailable":
        return "WATCHLIST", ["Layer A lolos; data broker tidak tersedia (cek ARJUM_API_KEY)"]
    reasons.append("Layer A (technical) lolos")
    if b_status == "pass":
        reasons.append("Layer B (akumulasi institusi/SS) lolos")
        if c_status == "pass":
            return "MAXIMUM_CONVICTION_BUY", reasons + ["Layer C (distribusi retail) terkonfirmasi"]
        return "STRONG_BUY", reasons + ["Layer C (distribusi retail) belum terkonfirmasi"]
    reasons.append(f"Layer B gagal: {b_fail_reason or 'broker tidak terakumulasi / harga di atas anchor'}")
    return "NEUTRAL_HOLD", reasons


# ------------------------------------------------------------------------ entry

async def analyze_stock(
    code: str, params: ScanParams, client: Optional[ArjumClient]
) -> StockVerdict:
    ticker = code.upper().removesuffix(".JK")
    error: Optional[str] = None

    # multi-year history when seasonality is requested (0 extra arjum quota)
    start_date = None
    if params.include_seasonality:
        start_date = (date.today() - timedelta(days=365 * 8)).isoformat()
    candles, history_error = await _fetch_history(
        ticker, params, client, period="1y", start_date=start_date
    )
    if not candles:
        error = history_error or f"Tidak ada data history untuk {ticker}"
        return StockVerdict(ticker=ticker, verdict="REJECTED", layers={}, error=error)

    a_pass, a_detail = _layer_a(candles, params)

    b_detail: dict = {"status": "unavailable", "details": {"reason": "ArjumClient tidak tersedia"}}
    c_detail: dict = {"status": "unavailable", "details": {"reason": "ArjumClient tidak tersedia"}}
    broker_flow: Optional[dict] = None
    anchor: Optional[float] = None

    # Quota optimization: arjum quota is precious (1000 req/day) — only spend it
    # on tickers that already pass the technical filter (Layer A).
    if client is not None and not a_pass:
        b_detail = {"status": "skipped", "details": {"reason": "Layer A gagal — panggilan broker dihemat (quota arjum)"}}
        c_detail = b_detail

    if client is not None and a_pass:
        try:
            end = date.today()
            start = end - timedelta(days=int(params.lookback_days * 1.6))
            raw = await client.broker_summary(
                ticker,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                broker_limit=max(params.top_n_brokers * 3, 20),
                flow=params.flow,
            )
            b_detail, c_detail = _layer_bc(raw, candles, params)
            broker_flow = {
                "stock_code": raw.get("stock_code", ticker),
                "flow": raw.get("flow"),
                "broker_start": raw.get("broker_start"),
                "broker_end": raw.get("broker_end"),
                "latest_date": raw.get("latest_date"),
                "layer_b": b_detail,
                "layer_c": c_detail,
            }
            anchor = b_detail["details"].get("buy_avg_anchor")
        except ArjumAuthError as exc:
            b_detail = {"status": "unavailable", "details": {"reason": str(exc)}}
            c_detail = b_detail
            error = str(exc)
        except ArjumError as exc:
            b_detail = {"status": "unavailable", "details": {"reason": str(exc)}}
            c_detail = b_detail
            error = str(exc)

    b_fail_reason = (
        b_detail.get("details", {}).get("reason")
        or b_detail.get("details", {}).get("match_rule")
    )
    verdict, reasons = _verdict(a_pass, b_detail["status"], c_detail["status"], b_fail_reason)

    plan = None
    if a_pass:
        lb = a_detail.get("lower_band")
        atr_v = a_detail.get("atr14")
        if lb is not None and atr_v is not None:
            plan = build_plan(a_detail["close"], float(lb), float(atr_v), params)
            if anchor is not None:
                plan["buy_avg_anchor"] = anchor

    # ---- extras (opt-in, 0 arjum quota) ----
    seasonality = monthly_seasonality(candles) if params.include_seasonality else None
    news: Optional[list] = None
    corp_actions: Optional[list] = None
    if params.include_news:
        news = await fetch_news(ticker)
        corp_actions = await fetch_corp_actions(ticker)

    stock = StockVerdict(
        ticker=ticker,
        verdict=verdict,
        layers={
            "a": {"status": "pass" if a_pass else "fail", "details": a_detail},
            "b": b_detail,
            "c": c_detail,
        },
        reasons=reasons,
        technicals=a_detail,
        broker_flow=broker_flow,
        plan=plan,
        error=error,
        seasonality=seasonality,
        news=news,
        corp_actions=corp_actions,
    )
    stock.explanation = explain_verdict(stock, params)
    return stock