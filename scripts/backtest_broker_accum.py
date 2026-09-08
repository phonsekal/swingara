"""Backtest: apakah konfirmasi akumulasi broker memperkuat sinyal Layer A?

Ide (bandarmologi): sinyal teknis (pullback + konfirmasi EMA5) lebih kuat bila
disertai akumulasi broker tertentu — mis. broker SS / broker smart money masuk
top net buyer pada periode yang sama. Data broker historis tersedia dari arjum
(broker-summary per tanggal), jadi kita bisa menguji hipotesis ini secara
kausal:

  untuk tiap ticker & tiap minggu historis (mundur N minggu):
    - hitung sinyal Layer A pada bar minggu itu (dari yfinance)
    - ambil broker-summary arjum untuk minggu yang sama (periode 1 minggu)
    - tentukan apakah broker target / smart money adalah net buyer
    - ukur forward return 5/10/20 hari sesudahnya
  lalu bandingkan distribusi return:
    sinyal A saja  vs  sinyal A + broker X net buy  vs  sinyal A + smart money net buy

Catatan kuota: 1 panggilan broker-summary per (ticker, minggu) — dengan 20 ticker
x 24 minggu = 480 panggilan (masuk budget harian 900). Gunakan --weeks lebih kecil
untuk hemat kuota.

Contoh:  PYTHONPATH=. .venv/bin/python scripts/backtest_broker_accum.py \
             --tickers BBRI,BMRI,TINS,ANTM,ADRO --weeks 12 --target SS
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, ".")

from app.arjum import ArjumClient, ArjumError
from app.broker_dir import broker_info, SMART_MONEY_CODES
from app.config import settings
from app.scanner import _history_from_yfinance
from app import technicals as ta
from app.yf_lock import yf_lock

# ---------------------------------------------------------------- disk cache
# Kuota harian arjum terbatas (1000 req) — simpan hasil broker-summary ke disk
# supaya run ulang (target/parameter berbeda) tidak membakar kuota lagi.
import json
import os
from pathlib import Path

_CACHE_FILE = Path(__file__).resolve().parent / ".broker_cache.json"
_cache: dict[str, dict] = {}
if _CACHE_FILE.exists():
    try:
        _cache = json.loads(_CACHE_FILE.read_text())
    except Exception:
        _cache = {}


def _cache_key(code: str, start: str, end: str) -> str:
    return f"{code}|{start}|{end}"


def _cache_get(code: str, start: str, end: str):
    return _cache.get(_cache_key(code, start, end))


def _cache_set(code: str, start: str, end: str, data: dict) -> None:
    _cache[_cache_key(code, start, end)] = data
    try:
        _CACHE_FILE.write_text(json.dumps(_cache))
    except Exception:
        pass



# ---------------------------------------------------------------- helpers

def layer_a_signal(candles: list[dict], i: int, params: dict) -> bool:
    close = np.asarray([c["close"] for c in candles], dtype=float)
    high = np.asarray([c["high"] for c in candles], dtype=float)
    low = np.asarray([c["low"] for c in candles], dtype=float)
    open_ = np.asarray([c["open"] for c in candles], dtype=float)
    ema20 = ta.ema(close, params.get("ema_period", 20))
    sma50 = ta.sma(close, params.get("sma_period", 50))
    ema5 = ta.ema(close, 5)
    _, _, lower = ta.bollinger(close, params.get("bb_period", 20), params.get("bb_std", 2.0))
    rsi14 = ta.rsi(close, 14)
    liq = _rolling_avg_value(close, np.asarray([c["volume"] for c in candles], dtype=float), 20)
    pull = _rolling_pullback(close, high, 20)
    if i < max(params.get("min_history_days", 60), 50, 20) - 1:
        return False
    if np.isnan(ema20[i]) or np.isnan(sma50[i]) or np.isnan(lower[i]) or np.isnan(rsi14[i]):
        return False
    tol = params.get("touch_tolerance_pct", 4.0)
    near_band = min(close[i], low[i]) <= lower[i] * (1.0 + tol / 100.0)
    gap = (close[i] - lower[i]) / lower[i] * 100.0 if lower[i] > 0 else 0.0
    gap_ok = params.get("band_gap_max_pct", 5.0) <= 0 or gap <= params.get("band_gap_max_pct", 5.0)
    rsi_ok = rsi14[i] < params.get("rsi_max", 65.0) and rsi14[i] <= 70
    conf = True
    if params.get("require_green_day", True):
        conf = conf and close[i] > open_[i]
    if params.get("require_close_above_ema5", True):
        conf = conf and np.isfinite(ema5[i]) and close[i] > ema5[i]
    return bool(
        close[i] > ema20[i] > sma50[i]
        and near_band
        and gap_ok
        and liq[i] > params.get("min_liquidity_idr", 1e9)
        and close[i] >= params.get("min_price", 100)
        and rsi_ok
        and (params.get("pullback_pct", 3.5) <= 0 or pull[i] >= params.get("pullback_pct", 3.5))
        and conf
    )


def _rolling_avg_value(close: np.ndarray, volume: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    for i in range(window - 1, len(close)):
        out[i] = float(np.mean(close[i - window + 1 : i + 1] * volume[i - window + 1 : i + 1]))
    return out


def _rolling_pullback(close: np.ndarray, high: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    for i in range(window - 1, len(close)):
        peak = float(np.max(high[i - window + 1 : i + 1]))
        if peak > 0:
            out[i] = (peak - close[i]) / peak * 100.0
    return out


def _stats(rets: list[float]) -> dict:
    if not rets:
        return {"n": 0}
    arr = np.asarray(rets)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    pf = wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else (None if not len(wins) else float("inf"))
    return {
        "n": len(arr),
        "avg": round(float(arr.mean()), 2),
        "median": round(float(np.median(arr)), 2),
        "win_rate": round(len(wins) / len(arr) * 100.0, 1),
        "pf": round(pf, 2) if pf is not None and np.isfinite(pf) else None,
        "std": round(float(arr.std()), 2),
    }


# ---------------------------------------------------------------- main

async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", default="BBRI,BMRI,TINS,ANTM,ADRO,TLKM,ASII,INCO,ICBP,KLBF,ACES,INDF,GGRM,NCKL,LPKR,BBTN,MDKA,PGAS,PTBA,SMGR")
    ap.add_argument("--weeks", type=int, default=24, help="berapa minggu ke belakang diuji")
    ap.add_argument("--target", default="SS", help="kode broker target (kosong = hanya smart money)")
    ap.add_argument("--fwd", type=int, default=10, help="forward return dalam hari")
    ap.add_argument("--freq", type=int, default=1, help="ambil sampel tiap N minggu (hemat kuota)")
    ap.add_argument("--loose", action="store_true", help="longgarkan gate (tanpa konfirmasi EMA5/hari hijau, pullback 2%) untuk sampel lebih besar")
    ap.add_argument("--min_pull", type=float, default=None, help="override pullback minimum (%)")
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    target = args.target.strip().upper()
    params = {
        "ema_period": 20, "sma_period": 50, "bb_period": 20, "bb_std": 2.0,
        "touch_tolerance_pct": 4.0, "band_gap_max_pct": 5.0, "rsi_max": 65.0,
        "pullback_pct": 3.5, "min_liquidity_idr": 1e9, "min_price": 100.0,
        "min_history_days": 60, "require_green_day": True, "require_close_above_ema5": True,
    }
    if args.loose:
        params["pullback_pct"] = 2.0
        params["require_green_day"] = False
        params["require_close_above_ema5"] = False
        params["touch_tolerance_pct"] = 5.0
        params["rsi_max"] = 70.0
    if args.min_pull is not None:
        params["pullback_pct"] = args.min_pull
    mode = "LOOSE" if args.loose else "TIGHT"
    print(f"Mode gate: {mode} — pullback>={params['pullback_pct']}%, tol={params['touch_tolerance_pct']}%, rsi<{params['rsi_max']}, konfirmasi={'ya' if params['require_close_above_ema5'] else 'tidak'}")
    target_info = broker_info(target) if target else None
    if target_info:
        print(f"Target broker {target}: {target_info['name']} — tags={target_info['tags']} group={target_info['group']}")

    client = ArjumClient(settings.arjum_api_key, base_url=settings.arjum_base_url, timeout=settings.request_timeout)
    end = date.today()
    # kumpulkan data sekali: sinyal per minggu + forward return (yfinance), lalu broker (arjum)
    agg = defaultdict(list)  # bucket -> list[forward_return]
    summary_rows: list[dict] = []

    sem = asyncio.Semaphore(8)
    all_rows: list[dict] = []

    async def one(ticker: str) -> None:
        # ---- history yfinance (1 panggilan per ticker, full window) ----
        try:
            start_date = (end - timedelta(days=365 * 2)).isoformat()
            candles = await _history_from_yfinance(ticker, 0, "1y", start_date)
        except Exception as exc:
            print(f"  {ticker}: yfinance gagal — {exc}")
            return
        closes = [c["close"] for c in candles]
        dates = [c["date"] for c in candles]
        n = len(closes)
        if n < 120:
            print(f"  {ticker}: hanya {n} bar, dilewati")
            return

        # ---- untuk tiap minggu (sampling mundur dari akhir) ----
        for week_idx in range(0, args.weeks, args.freq):
            bar = n - 1 - week_idx * 5
            if bar < 60:
                break
            bar_date = dates[bar]
            try:
                bar_dt = date.fromisoformat(bar_date)
            except ValueError:
                continue
            wk_start = (bar_dt - timedelta(days=6)).isoformat()
            wk_end = bar_dt.isoformat()

            sig = layer_a_signal(candles, bar, params)

            # forward return
            fwd_bar = bar + args.fwd
            if fwd_bar >= n:
                continue
            fwd_ret = (closes[fwd_bar] / closes[bar] - 1.0) * 100.0

            # ---- broker-summary untuk minggu yang sama (arjum, 1 panggilan) ----
            # Dicatat untuk SEMUA ticker-minggu (bukan hanya sinyal Layer A) agar
            # korelasi umum broker->return bisa diukur; --freq menghemat kuota.
            cached = _cache_get(ticker, wk_start, wk_end)
            if cached is not None:
                raw = cached
            else:
                async with sem:
                    try:
                        raw = await client.broker_summary(ticker, start_date=wk_start, end_date=wk_end, broker_limit=30, flow="all")
                        _cache_set(ticker, wk_start, wk_end, raw)
                    except (ArjumError, Exception):
                        continue
            brokers = raw.get("brokers") or []
            nval_map = {str(b.get("broker_code", "")).upper(): float(b.get("nval") or 0.0) for b in brokers}
            top_buyers = sorted(
                [b for b in brokers if float(b.get("nval") or 0.0) > 0],
                key=lambda b: float(b.get("nval") or 0.0),
                reverse=True,
            )[:3]
            top_buyer_codes = {str(b.get("broker_code", "")).upper() for b in top_buyers}
            smart_hit = bool(top_buyer_codes & SMART_MONEY_CODES)
            target_hit = target and nval_map.get(target, 0.0) > 0
            top_buyer_total = sum(float(b.get("nval") or 0.0) for b in top_buyers)

            # simpan net value 5 broker teratas per minggu untuk breakdown per broker
            top5 = sorted(
                brokers, key=lambda b: float(b.get("nval") or 0.0), reverse=True
            )[:5]
            broker_nets = {
                str(b.get("broker_code", "")).upper(): round(float(b.get("nval") or 0.0) / 1e9, 1)
                for b in top5
            }
            all_rows.append(
                {
                    "ticker": ticker, "date": bar_date, "fwd_ret": round(fwd_ret, 2),
                    "sig": bool(sig),
                    "target_net": round(nval_map.get(target, 0.0) / 1e9, 1) if target else None,
                    "smart_hit": smart_hit, "target_hit": target_hit,
                    "top_buyers": ",".join(sorted(top_buyer_codes)),
                    "top_buyer_total_G": round(top_buyer_total / 1e9, 1),
                    "broker_nets": broker_nets,
                }
            )

    await asyncio.gather(*(one(t) for t in tickers))
    await client.close()

    # ---- hasil: matriks 2x2 (Layer A x broker) + korelasi umum ----
    print(f"\n=== Hasil: {len(tickers)} ticker, {args.weeks} minggu, fwd {args.fwd} hari ===")
    print(f"Mode gate: {mode} — pullback>={params['pullback_pct']}%, tol={params['touch_tolerance_pct']}%, rsi<{params['rsi_max']}")
    print(f"Total observasi (ticker-minggu): {len(all_rows)}")
    print()
    print(f"{'Bucket':<32} {'n':>4} {'avg%':>7} {'median%':>8} {'win%':>6} {'PF':>6}")

    def _show(bucket, rows_):
        rets = [r["fwd_ret"] for r in rows_]
        s = _stats(rets)
        if s["n"]:
            print(f"{bucket:<32} {s['n']:>4} {s['avg']:>7} {s['median']:>8} {s['win_rate']:>6} {str(s['pf']):>6}")

    _show("Semua ticker-minggu", all_rows)
    sig_rows = [r for r in all_rows if r["sig"]]
    _show("Sinyal Layer A saja", sig_rows)
    _show("  + smart money top buyer", [r for r in sig_rows if r["smart_hit"]])
    _show("  + smart money BUKAN buyer", [r for r in sig_rows if not r["smart_hit"]])
    if target:
        _show(f"  + {target} net buy", [r for r in sig_rows if r["target_hit"]])
        _show(f"  + {target} net sell/flat", [r for r in sig_rows if not r["target_hit"]])
    print()
    _show("Smart money top buyer (tanpa gate)", [r for r in all_rows if r["smart_hit"]])
    _show("Smart money BUKAN top buyer", [r for r in all_rows if not r["smart_hit"]])
    if target:
        _show(f"{target} net buy (tanpa gate)", [r for r in all_rows if r["target_hit"]])
        _show(f"{target} net sell/flat (tanpa gate)", [r for r in all_rows if not r["target_hit"]])
        _show(f"{target} net buy besar >10M (tanpa gate)", [r for r in all_rows if (r.get("target_net") or 0) > 10])

    # ---- breakdown per broker: apakah net buy broker X di minggu t memprediksi return? ----
    broker_stats: dict[str, dict] = {}
    for r in all_rows:
        fwd = r["fwd_ret"]
        for code, net_g in (r.get("broker_nets") or {}).items():
            if net_g <= 0:
                continue
            st = broker_stats.setdefault(code, {"n": 0, "rets": []})
            st["n"] += 1
            st["rets"].append(fwd)
    print()
    print("=== Breakdown per broker (minggu di mana broker itu NET BUY) ===")
    print(f"{'Broker':<8} {'n':>4} {'avg%':>7} {'median%':>8} {'win%':>6} {'PF':>6}")
    for code in sorted(broker_stats, key=lambda c: -broker_stats[c]["n"]):
        st = broker_stats[code]
        if st["n"] < 10:
            continue
        s = _stats(st["rets"])
        print(f"{code:<8} {s['n']:>4} {s['avg']:>7} {s['median']:>8} {s['win_rate']:>6} {str(s['pf']):>6}")

    if all_rows:
        print("\nContoh baris sinyal Layer A (10 teratas by |fwd_ret|):")
        rows = sorted(sig_rows, key=lambda r: abs(r["fwd_ret"]), reverse=True)[:10]
        for r in rows:
            tgt = f"{r.get('target_net')}G" if r.get("target_net") is not None else "-"
            print(f"  {r['ticker']:5s} {r['date']} fwd={r['fwd_ret']:+.2f}% {target}={tgt:>7} smart={r['smart_hit']} buyers={r['top_buyers']}")


if __name__ == "__main__":
    asyncio.run(main())