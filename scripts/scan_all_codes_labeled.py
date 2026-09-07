#!/usr/bin/env python3
"""Offline Layer-A scan across all mapped codes with style labeling.

Runs multiple parameter variants and labels each Layer A pass as:
- strong_buy: stricter variant, more conviction-like
- buy: looser variant, still passes but less strict

It is purely yfinance Layer A, so no arjum key is needed.

Usage:
  python3 scripts/scan_all_codes_labeled.py > /tmp/scan_all_codes_labeled.txt
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

from app.models import ScanParams
from app.technicals import sma, ema, bollinger, atr, rsi, avg_transaction_value, pullback_pct, close_near_lower_band
from app.universe import all_mapped_tickers
import numpy as np


def layer_a_passes(candles: list[dict], params: ScanParams) -> tuple[bool, dict]:
    """Pure Layer A check without the full scanner wrapper."""
    close = np.asarray([c["close"] for c in candles], dtype=float)
    high = np.asarray([c["high"] for c in candles], dtype=float)
    low = np.asarray([c["low"] for c in candles], dtype=float)
    volume = np.asarray([c["volume"] for c in candles], dtype=float)
    n = len(candles)
    if n < int(params.min_history_days):
        return False, {"reason": "min_history_days"}

    ema20 = ema(close, params.ema_period)
    sma50 = sma(close, params.sma_period)
    _, _, lower = bollinger(close, params.bb_period, params.bb_std)
    atr14 = atr(high, low, close, 14)
    rsi14 = rsi(close, 14)
    touch_any = close_near_lower_band(close, lower, params.touch_window_days)

    last = n - 1
    price = float(close[last])
    e20 = float(ema20[last])
    s50 = float(sma50[last])
    lb = float(lower[last])
    r = float(rsi14[last])
    liq = avg_transaction_value(close, volume, 20)
    pull = pullback_pct(close, high, 20)

    passed = all([
        price > e20 > s50,
        min(price, float(low[last])) <= lb * (1.0 + params.touch_tolerance_pct / 100.0),
        liq > params.min_liquidity_idr,
        price >= params.min_price,
        (params.max_price is None or price <= params.max_price),
        (params.rsi_max <= 0 or r < params.rsi_max),
        (params.pullback_pct <= 0 or pull >= params.pullback_pct),
        bool(touch_any[last]),
    ])
    return passed, {
        "close": round(price, 0),
        "ema20": round(e20, 0) if e20 == e20 else None,
        "sma50": round(s50, 0) if s50 == s50 else None,
        "lower_band": round(lb, 0) if lb == lb else None,
        "rsi14": round(r, 1) if r == r else None,
        "avg_20d_value_idr": round(liq, 0) if liq == liq else None,
        "pullback_from_20d_high_pct": round(pull, 2) if pull == pull else None,
        "pass": passed,
    }


async def run_all(*, params: ScanParams) -> list[dict]:
    tickers = all_mapped_tickers()
    results: list[dict] = []
    t0 = time.time()
    for i, code in enumerate(tickers, 1):
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
            dates = [str(idx)[:10] for idx in df.index]

            n = len(close)
            if n < int(params.min_history_days):
                results.append({"ticker": code, "verdict": "REJECTED", "error": "min_history_days", "layer_a": {"close": round(float(close[-1]), 0), "pass": False, "reason": "min_history_days"}})
                continue

            ema20 = ema(close, params.ema_period)
            sma50 = sma(close, params.sma_period)
            _, _, lower = bollinger(close, params.bb_period, params.bb_std)
            atr14 = atr(high, low, close, 14)
            rsi14 = rsi(close, 14)
            touch_any = close_near_lower_band(close, lower, params.touch_window_days)

            last = n - 1
            price = float(close[last])
            e20 = float(ema20[last])
            s50 = float(sma50[last])
            lb = float(lower[last])
            r = float(rsi14[last])
            liq = float(avg_transaction_value(close, volume, 20))
            pull = float(pullback_pct(close, high, 20))

            passed = all([
                price > e20 > s50,
                min(price, float(low[last])) <= lb * (1.0 + params.touch_tolerance_pct / 100.0),
                liq > params.min_liquidity_idr,
                price >= params.min_price,
                (params.max_price is None or price <= params.max_price),
                (params.rsi_max <= 0 or r < params.rsi_max),
                (params.pullback_pct <= 0 or pull >= params.pullback_pct),
                bool(touch_any[last]),
            ])
            results.append({"ticker": code, "verdict": "PASS" if passed else "REJECTED", "layer_a": {
                "close": round(price, 0),
                "ema20": round(e20, 0) if e20 == e20 else None,
                "sma50": round(s50, 0) if s50 == s50 else None,
                "lower_band": round(lb, 0) if lb == lb else None,
                "rsi14": round(r, 1) if r == r else None,
                "avg_20d_value_idr": round(liq, 0) if liq == liq else None,
                "pullback_from_20d_high_pct": round(pull, 2) if pull == pull else None,
                "pass": passed,
            }})
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            results.append({"ticker": code, "verdict": "ERROR", "error": str(exc)})
        if i % 10 == 0 or i == len(tickers):
            elapsed = time.time() - t0
            print(f"[{i:>4}/{len(tickers)}] {code:<8} {results[-1].get('verdict')} elapsed={elapsed:.0f}s", flush=True)

    print(f"\nDone {len(tickers)} tickers in {time.time() - t0:.0f}s", flush=True)
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


def style_label(layer_a: dict) -> str:
    """Crude style label based on how conviction-like the setup looks.

    Stronger setup:
      - RSI meaningfully below max threshold
      - pullback deep enough to look like a real correction
      - close reasonably close to lower band or below EMA20 cushion smaller
    Weaker setup:
      - RSI near the ceiling
      - pullback shallow
      - close far above lower band (band touch recent/weak)
    """
    rsi_max = 60.0  # should match params used; kept here as label reference
    rsi = layer_a.get("rsi14")
    pull = layer_a.get("pullback_from_20d_high_pct")
    close = layer_a.get("close")
    lb = layer_a.get("lower_band")

    reasons: list[str] = []
    strong = True

    if rsi is None or pull is None or lb is None or close is None:
        return "buy (insufficient detail)"

    if rsi > rsi_max - 10:
        strong = False
        reasons.append("RSI dekat batas maks")

    if (pull or 0) < 4.0:
        strong = False
        reasons.append("pullback shallow")

    band_gap_pct = 0.0
    if lb and lb > 0:
        band_gap_pct = (close - lb) / lb * 100.0
    if band_gap_pct > 3.0:
        strong = False
        reasons.append("harga agak jauh dari lower band")

    if strong:
        return "strong_buy"
    return "buy (" + ", ".join(reasons) + ")"


async def main() -> None:
    variants = [
        ("strict", {
            "min_liquidity_idr": 5_000_000_000.0,
            "rsi_max": 60.0,
            "pullback_pct": 3.0,
            "touch_tolerance_pct": 1.0,
            "touch_window_days": 5,
        }),
        ("looser", {
            "min_liquidity_idr": 1_000_000_000.0,
            "rsi_max": 65.0,
            "pullback_pct": 2.0,
            "touch_tolerance_pct": 2.0,
            "touch_window_days": 3,
        }),
    ]
    all_passes: dict[str, dict] = {}
    for name, overrides in variants:
        params = ScanParams(
            data_source="yfinance",
            lookback_days=15,
            top_n_brokers=3,
            price_anchor_pct=3.0,
            min_price=100.0,
            max_price=None,
            min_history_days=60,
            rsi_max=overrides.get("rsi_max", 60.0),
            pullback_pct=overrides.get("pullback_pct", 3.0),
            min_liquidity_idr=overrides.get("min_liquidity_idr", 5_000_000_000.0),
            touch_tolerance_pct=overrides.get("touch_tolerance_pct", 1.0),
            touch_window_days=overrides.get("touch_window_days", 5),
            retail_brokers=["YP", "CC", "NI"],
            retail_share_min=0.5,
            tp1_pct=5.0,
            tp2_pct=10.0,
            sl_pct=5.0,
            atr_stop_mult=2.0,
            risk_per_trade_pct=2.0,
            portfolio_idr=100_000_000.0,
        )

        results = await run_all(params=params)
        summary = summarize(results)

        passed = summary.get("layer_a_pass_codes", [])
        print(f"\n=== VARIANT: {name} ===", flush=True)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        if passed:
            print("\nLayer A pass codes:", flush=True)
            for code in passed:
                print(f"  {code}", flush=True)
                all_passes[code] = {"variant": name, "layer_a": next(r.get("layer_a") for r in results if r.get("ticker") == code)}
        else:
            print("\nNo Layer A pass codes.", flush=True)

        path = Path(f"/tmp/scan_all_codes_{name}.json")
        path.write_text(json.dumps({"params": params.model_dump(), "summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved to {path}", flush=True)

        tail_path = Path(f"/tmp/scan_all_codes_{name}_tail.txt")
        tail_path.write_text("\n".join(f"{r.get('ticker')} -> {r.get('verdict')}" for r in results), encoding="utf-8")
        print(f"Saved per-ticker verdicts to {tail_path}", flush=True)

    print("\n=== COMBINED PASS LIST ===", flush=True)
    combined = sorted(all_passes.items())
    print(f"Total distinct Layer A passes across variants: {len(combined)}", flush=True)
    for code, info in combined:
        label = style_label(info["layer_a"])
        print(f"  {code:<8} {info['variant']:<8} {label}", flush=True)

    combined_path = Path("/tmp/scan_all_codes_labeled.json")
    combined_path.write_text(json.dumps({
        "variants": {
            name: {"params": params.model_dump(), "summary": summary, "results": results}
            for name, summary, params, results in (
                (a[0], a[1]["summary"], a[1]["params"], a[1]["results"])
                for a in [
                    ("strict", {"summary": summarize(results), "params": params, "results": results})
                    for params, results in [
                        (ScanParams(data_source="yfinance", lookback_days=15, top_n_brokers=3, price_anchor_pct=3.0, min_price=100.0, max_price=None, min_history_days=60, rsi_max=overrides.get("rsi_max", 60.0), pullback_pct=overrides.get("pullback_pct", 3.0), min_liquidity_idr=overrides.get("min_liquidity_idr", 5_000_000_000.0), touch_tolerance_pct=overrides.get("touch_tolerance_pct", 1.0), touch_window_days=overrides.get("touch_window_days", 5), retail_brokers=["YP","CC","NI"], retail_share_min=0.5, tp1_pct=5.0, tp2_pct=10.0, sl_pct=5.0, atr_stop_mult=2.0, risk_per_trade_pct=2.0, portfolio_idr=100_000_000.0), await run_all(params=ScanParams(data_source="yfinance", lookback_days=15, top_n_brokers=3, price_anchor_pct=3.0, min_price=100.0, max_price=None, min_history_days=60, rsi_max=overrides.get("rsi_max", 60.0), pullback_pct=overrides.get("pullback_pct", 3.0), min_liquidity_idr=overrides.get("min_liquidity_idr", 5_000_000_000.0), touch_tolerance_pct=overrides.get("touch_tolerance_pct", 1.0), touch_window_days=overrides.get("touch_window_days", 5), retail_brokers=["YP","CC","NI"], retail_share_min=0.5, tp1_pct=5.0, tp2_pct=10.0, sl_pct=5.0, atr_stop_mult=2.0, risk_per_trade_pct=2.0, portfolio_idr=100_000_000.0)))
                        for overrides in [
                            {"min_liquidity_idr": 5_000_000_000.0, "rsi_max": 60.0, "pullback_pct": 3.0, "touch_tolerance_pct": 1.0, "touch_window_days": 5},
                            {"min_liquidity_idr": 1_000_000_000.0, "rsi_max": 65.0, "pullback_pct": 2.0, "touch_tolerance_pct": 2.0, "touch_window_days": 3},
                        ]
                    ]
                ]
            )
        },
        "combined_passes": combined,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved combined pass list to {combined_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
