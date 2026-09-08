#!/usr/bin/env python3
"""Layer A method variants across the widest available universe.

Purpose
- Answer “most optimal / higher win-rate” by letting the same underlying
  technical layer be evaluated under several clearly named rules, not one
  giant all-or-nothing gate.
- Widen the search beyond the static mapped 300 so the result is not limited
  to a curated list when we are looking for the best candidates.

Important scope note
- This script is a directional optimizer helper. It ranks candidates under
  each method and shows which ones pass stricter vs looser definitions.
- It does not claim a future win rate by itself. Win rate comes from a proper
  multi-year backtest of the entry/exit rule, not from a single snapshot scan.

Run:
  python3 scripts/scan_all_codes_variants.py
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

sys_path = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(sys_path))

import numpy as np

from app.models import ScanParams
from app.technicals import ema, sma, bollinger, rsi, avg_transaction_value, pullback_pct
from app.universe import all_mapped_tickers, fetch_universe, group_of

# ---------------------------------------------------------------------------
# Method definitions
# ---------------------------------------------------------------------------
# Each method is a plain dict of Layer A knobs plus a one-line thesis.
# The same underlying check function is reused, so the only difference
# between methods is how strict/loose the gates are.

METHODS = [
    {
        "name": "strict_strong_buy",
        "description": "Conviction-only: uptrend + pullback >= 4.5% + low dekat lower band (<= 2.5%) + RSI <= 55 + konfirmasi berbalik (close > EMA5, hari hijau). Paling ketat — hanya setup dalam (PF 1.25, 5 thn).",
        "min_liquidity_idr": 5_000_000_000.0,
        "rsi_max": 55.0,
        "pullback_pct": 4.5,
        "touch_tolerance_pct": 2.5,
        "gap_max_pct": 4.0,
        "min_price": 100.0,
        "require_close_above_ema5": True,
        "require_green_day": True,
    },
    {
        "name": "buy_quality_tighter",
        "description": "Quality buy: uptrend + pullback >= 4% + low <= 3.5% dari lower band + RSI <= 60 + konfirmasi berbalik (PF 1.17, 5 thn, 30 saham).",
        "min_liquidity_idr": 5_000_000_000.0,
        "rsi_max": 60.0,
        "pullback_pct": 4.0,
        "touch_tolerance_pct": 3.5,
        "gap_max_pct": 5.0,
        "min_price": 100.0,
        "require_close_above_ema5": True,
        "require_green_day": True,
    },
    {
        "name": "band_proximity_main",
        "description": "Main method: pullback >= 3.5% + low <= 4% dari lower band + RSI <= 65 + konfirmasi berbalik — sweet spot (PF 1.06, win 48%, 5 thn).",
        "min_liquidity_idr": 5_000_000_000.0,
        "rsi_max": 65.0,
        "pullback_pct": 3.5,
        "touch_tolerance_pct": 4.0,
        "gap_max_pct": 5.0,
        "min_price": 100.0,
        "require_close_above_ema5": True,
        "require_green_day": True,
    },
    {
        "name": "wide_candidate_pool",
        "description": "Broad candidate pool: pullback >= 4% + low <= 3.5% dari lower band + RSI <= 70, harga murah & likuiditas lebih rendah boleh masuk (PF 1.12).",
        "min_liquidity_idr": 1_000_000_000.0,
        "rsi_max": 70.0,
        "pullback_pct": 4.0,
        "touch_tolerance_pct": 3.5,
        "gap_max_pct": 6.0,
        "min_price": 50.0,
        "require_close_above_ema5": True,
        "require_green_day": True,
    },
]


def layer_a_passes(
    candles: list[dict],
    params: ScanParams,
    method: dict,
) -> tuple[bool, dict]:
    """Pure Layer A check for one named method (band-gap cap + confirmation).

    Mirrors app/scanner._layer_a under the multi-method path: same gates,
    including the backtest-backed entry confirmation (close > EMA5 / green day).
    """
    gap_max_pct = method.get("gap_max_pct", 0.0)
    close = np.asarray([c["close"] for c in candles], dtype=float)
    high = np.asarray([c["high"] for c in candles], dtype=float)
    low = np.asarray([c["low"] for c in candles], dtype=float)
    open_ = np.asarray([c["open"] for c in candles], dtype=float)
    volume = np.asarray([c["volume"] for c in candles], dtype=float)
    n = len(candles)
    if n < int(params.min_history_days):
        return False, {"reason": "min_history_days"}

    ema20 = ema(close, params.ema_period)
    sma50 = sma(close, params.sma_period)
    ema5 = ema(close, 5)
    _, _, lower = bollinger(close, params.bb_period, params.bb_std)
    rsi14 = rsi(close, 14)

    last = n - 1
    price = float(close[last])
    e20 = float(ema20[last])
    s50 = float(sma50[last])
    e5 = float(ema5[last])
    lb = float(lower[last])
    r = float(rsi14[last])
    liq = float(avg_transaction_value(close, volume, 20))
    pull = float(pullback_pct(close, high, 20))
    open_last = float(open_[last])

    band_gap = None
    if lb and lb > 0:
        band_gap = (price - lb) / lb * 100.0

    confirmation_ok = True
    if method.get("require_close_above_ema5"):
        confirmation_ok = confirmation_ok and not np.isnan(e5) and price > e5
    if method.get("require_green_day"):
        confirmation_ok = confirmation_ok and price > open_last

    passed = all([
        price > e20 > s50,
        liq > params.min_liquidity_idr,
        price >= params.min_price,
        (params.max_price is None or price <= params.max_price),
        (params.rsi_max <= 0 or r < params.rsi_max),
        (params.pullback_pct <= 0 or pull >= params.pullback_pct),
        band_gap is not None and band_gap <= gap_max_pct,
        confirmation_ok,
    ])
    return passed, {
        "close": round(price, 0),
        "ema20": round(e20, 0) if e20 == e20 else None,
        "sma50": round(s50, 0) if s50 == s50 else None,
        "lower_band": round(lb, 0) if lb == lb else None,
        "rsi14": round(r, 1) if r == r else None,
        "avg_20d_value_idr": round(liq, 0) if liq == liq else None,
        "pullback_from_20d_high_pct": round(pull, 2) if pull == pull else None,
        "band_gap_pct": round(band_gap, 2) if band_gap == band_gap else None,
        "pass": passed,
    }


async def run_all(*, params: ScanParams, method: dict) -> list[dict]:
    """Scan a wide universe through yfinance Layer A only.

    Uses the mapped list as a first pass, then falls back to the wider
    market-cap universe when the arjum key is available.
    """
    tickers = all_mapped_tickers()
    results: list[dict] = []
    t0 = time.time()
    seen: set[str] = set()

    for i, code in enumerate(tickers, 1):
        if code.upper() in seen:
            continue
        seen.add(code.upper())
        try:
            import yfinance as yf
            from app.yf_lock import yf_lock

            with yf_lock:
                df = yf.download(f"{code}.JK", period="1y", progress=False)
            if df is None or df.empty:
                results.append({"ticker": code, "verdict": "REJECTED", "error": "no yfinance data"})
                continue

            def _col(key: str) -> np.ndarray:
                for col in df.columns:
                    name = col[0] if isinstance(col, tuple) else str(col)
                    name = str(name).lower().split(",")[0].strip()
                    if name == key.lower():
                        arr = df[col].astype(float).to_numpy(dtype=float)
                        if arr.ndim > 1:
                            arr = arr.ravel()
                        return arr
                raise RuntimeError(f"yfinance missing column {key} for {code}.JK")

            close = _col("Close")
            high = _col("High")
            low = _col("Low")
            volume = _col("Volume")
            volume = np.nan_to_num(volume)

            candles = [
                {"date": str(idx)[:10], "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v)}
                for idx, o, h, l, c, v in zip(df.index, _col("Open"), high, low, close, volume)
            ]

            passed, la = layer_a_passes(candles, params, method)
            results.append({"ticker": code, "verdict": "PASS" if passed else "REJECTED", "layer_a": la})
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            results.append({"ticker": code, "verdict": "ERROR", "error": str(exc)})
        if i % 10 == 0 or i == len(tickers):
            elapsed = time.time() - t0
            print(f"[{i:>4}/{len(tickers)}] {code:<8} {results[-1].get('verdict')} elapsed={elapsed:.0f}s", flush=True)

    # Widen to the market-cap universe when arjum is available.
    try:
        from app.arjum import ArjumClient

        client = ArjumClient()
        universe_rows = await fetch_universe(client, min_market_cap_idr=0.0, max_tickers=1000)
        wider = [r["code"] for r in universe_rows if r["code"].upper() not in seen]
        print(f"\nWider universe after mapped pass: {len(wider)} additional codes", flush=True)

        for i, code in enumerate(wider, 1):
            try:
                with yf_lock:
                    df = yf.download(f"{code}.JK", period="1y", progress=False)
                if df is None or df.empty:
                    results.append({"ticker": code, "verdict": "REJECTED", "error": "no yfinance data"})
                    continue

                def _col(key: str) -> np.ndarray:
                    for col in df.columns:
                        name = col[0] if isinstance(col, tuple) else str(col)
                        name = str(name).lower().split(",")[0].strip()
                        if name == key.lower():
                            arr = df[col].astype(float).to_numpy(dtype=float)
                            if arr.ndim > 1:
                                arr = arr.ravel()
                            return arr
                    raise RuntimeError(f"yfinance missing column {key} for {code}.JK")

                close = _col("Close")
                high = _col("High")
                low = _col("Low")
                volume = _col("Volume")
                volume = np.nan_to_num(volume)

                candles = [
                    {"date": str(idx)[:10], "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v)}
                    for idx, o, h, l, c, v in zip(df.index, _col("Open"), high, low, close, volume)
                ]

                passed, la = layer_a_passes(candles, params, method)
                results.append({"ticker": code, "verdict": "PASS" if passed else "REJECTED", "layer_a": la})
                seen.add(code.upper())
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                results.append({"ticker": code, "verdict": "ERROR", "error": str(exc)})
            if i % 10 == 0 or i == len(wider):
                elapsed = time.time() - t0
                print(f"[{i:>4}/{len(wider)}] {code:<8} {results[-1].get('verdict')} elapsed={elapsed:.0f}s", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"\nWider-universe extension skipped: {exc}", flush=True)

    print(f"\nDone {len(results)} tickers in {time.time() - t0:.0f}s", flush=True)
    return results


def summarize(results: list[dict]) -> dict:
    counts: dict[str, int] = {}
    passes: list[str] = []
    for r in results:
        v = r.get("verdict") or "UNKNOWN"
        counts[v] = counts.get(v, 0) + 1
        if r.get("layer_a", {}).get("pass"):
            passes.append(r.get("ticker", ""))
    return {
        "total": len(results),
        "by_verdict": counts,
        "layer_a_pass": len(passes),
        "layer_a_pass_codes": passes,
    }


def style_label(layer_a: dict, method: dict) -> str:
    """Crude conviction-style label relative to the method’s own ruler."""
    rsi_max = method.get("rsi_max", 60.0)
    rsi = layer_a.get("rsi14")
    pull = layer_a.get("pullback_from_20d_high_pct")
    gap = layer_a.get("band_gap_pct")

    if rsi is None or pull is None or gap is None:
        return "buy (insufficient detail)"

    reasons: list[str] = []
    strong = True

    if rsi > rsi_max - 5:
        strong = False
        reasons.append("RSI dekat batas maks")

    if pull < 3.0:
        strong = False
        reasons.append("pullback dangkal")

    if gap > 2.0:
        strong = False
        reasons.append("harga agak jauh dari lower band")

    if strong:
        return "strong_buy"
    return "buy (" + ", ".join(reasons) + ")"


async def main() -> None:
    all_passes: dict[str, dict] = {}

    for method in METHODS:
        params = ScanParams(
            data_source="yfinance",
            lookback_days=15,
            top_n_brokers=3,
            price_anchor_pct=3.0,
            min_price=method.get("min_price", 100.0),
            max_price=None,
            min_history_days=60,
            rsi_max=method.get("rsi_max", 60.0),
            pullback_pct=method.get("pullback_pct", 3.0),
            min_liquidity_idr=method.get("min_liquidity_idr", 5_000_000_000.0),
            touch_tolerance_pct=method.get("touch_tolerance_pct", 1.0),
            touch_window_days=5,
            retail_brokers=["YP", "CC", "NI"],
            retail_share_min=0.5,
            tp1_pct=5.0,
            tp2_pct=10.0,
            sl_pct=5.0,
            atr_stop_mult=2.0,
            risk_per_trade_pct=2.0,
            portfolio_idr=100_000_000.0,
        )

        results = await run_all(params=params, method=method)
        summary = summarize(results)

        print("\n=== METHOD:", method["name"], "===")
        print(method["description"])
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        passed = summary.get("layer_a_pass_codes", [])
        if passed:
            print("\nMethod pass codes:", flush=True)
            for code in passed:
                la = next(r.get("layer_a") for r in results if r.get("ticker") == code)
                label = style_label(la, method)
                print(f"  {code:<8} {label}", flush=True)
                all_passes[code] = {"method": method["name"], "layer_a": la}
        else:
            print("\nNo method passes this snapshot.", flush=True)

        path = Path(f"/tmp/scan_all_codes_{method['name']}.json")
        path.write_text(
            json.dumps({"method": method, "params": params.model_dump(), "summary": summary, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nSaved to {path}", flush=True)

    print("\n=== COMBINED PASS LIST ===", flush=True)
    combined = sorted(all_passes.items())
    print(f"Total distinct method passes across variants: {len(combined)}", flush=True)
    for code, info in combined:
        label = style_label(info["layer_a"], METHODS[0])  # reference ruler
        print(f"  {code:<8} {info['method']:<22} {label}", flush=True)

    combined_path = Path("/tmp/scan_all_codes_variants.json")
    combined_path.write_text(json.dumps({"methods": [m["name"] for m in METHODS], "combined_passes": combined}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved combined pass list to {combined_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
