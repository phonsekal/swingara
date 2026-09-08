"""Aktivitas satu broker di banyak saham (bandarmologi horizontal).

Menjawab: "broker SS minggu ini aktif apa saja — beli apa, jual apa, di harga
berapa". Untuk tiap saham di universe terpilih kita ambil broker-summary arjum
(cache TTL 600s per saham), filter baris kode broker yang dicari, lalu
lengkapi dengan harga pasar terakhir dari satu batch download yfinance
(0 kuota arjum).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from .arjum import ArjumClient, ArjumError
from .yf_lock import yf_lock

logger = logging.getLogger(__name__)

MAX_TICKERS_DEFAULT = 30
MAX_TICKERS_LIMIT = 100


async def _batch_close_prices(tickers: list[str]) -> dict[str, Optional[float]]:
    """Close terakhir untuk semua ticker dalam satu panggilan yfinance (0 quota)."""
    if not tickers:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        return {}

    def _download():
        with yf_lock:
            df = yf.download(
                [f"{t}.JK" for t in tickers],
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=False,
            )
        return df

    try:
        df = await asyncio.to_thread(_download)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("yfinance batch close gagal: %s", exc)
        return {}
    if df is None or df.empty:
        return {}

    closes: dict[str, Optional[float]] = {}
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover
        pd = None
    if pd is not None and isinstance(df.columns, pd.MultiIndex):
        # MultiIndex level 0 berisi "TINS.JK" — cocokkan dengan suffix .JK
        for t in tickers:
            try:
                series = df[f"{t}.JK"]["Close"].dropna()
                if len(series):
                    closes[t] = float(series.iloc[-1])
            except (KeyError, IndexError, TypeError):
                closes[t] = None
    else:
        for t in tickers:
            try:
                series = df["Close"].dropna()
                if len(series):
                    closes[t] = float(series.iloc[-1])
            except (KeyError, IndexError, TypeError):
                closes[t] = None
    return closes


async def broker_activity(
    tickers: list[str],
    broker: str,
    days: int,
    client: ArjumClient,
) -> dict:
    """Scan broker-summary per saham, kumpulkan aktivitas `broker` di periode `days`.

    Returns:
        {
          "broker": "SS",
          "days": 7,
          "start": "2026-09-01",
          "end": "2026-09-08",
          "activities": [
             {ticker, broker_code, broker_name, bval, sval, nval, nvol,
              bfrq, sfrq, close, broker_start, broker_end},
             ...
          ],
          "scanned": N,
          "errors": [ticker,...],
        }
    """
    broker = broker.strip().upper()
    end = date.today()
    start = end - timedelta(days=days)
    start_s = start.isoformat()
    end_s = end.isoformat()

    sem = asyncio.Semaphore(8)

    async def one(code: str) -> tuple[bool, Optional[dict]]:
        """(fetch_ok, activity). fetch_ok=False -> error fetch; activity None -> broker tidak aktif."""
        async with sem:
            try:
                raw = await client.broker_summary(
                    code.removesuffix(".JK"),
                    start_date=start_s,
                    end_date=end_s,
                    broker_limit=200,
                    flow="all",
                )
            except ArjumError as exc:
                logger.debug("broker_summary %s gagal: %s", code, exc)
                return False, None
            rows = raw.get("brokers") or []
            hit = next(
                (r for r in rows if str(r.get("broker_code", "")).upper() == broker),
                None,
            )
            if hit is None:
                return True, None
            return True, {
                "ticker": code.removesuffix(".JK"),
                "broker_code": broker,
                "broker_name": hit.get("broker_name", ""),
                "bval": float(hit.get("bval") or 0.0),
                "sval": float(hit.get("sval") or 0.0),
                "nval": float(hit.get("nval") or 0.0),
                "nvol": float(hit.get("nvol") or 0.0),
                "bfrq": int(hit.get("bfrq") or 0),
                "sfrq": int(hit.get("sfrq") or 0),
                "broker_start": raw.get("broker_start") or start_s,
                "broker_end": raw.get("broker_end") or end_s,
            }

    results = list(await asyncio.gather(*(one(t) for t in tickers)))
    activities = [r for ok, r in results if ok and r is not None]
    errors = [t for t, (ok, _r) in zip(tickers, results) if not ok]

    # harga pasar terakhir — satu batch yfinance untuk semua ticker yang aktif
    if activities:
        prices = await _batch_close_prices([a["ticker"] for a in activities])
        for a in activities:
            a["close"] = prices.get(a["ticker"])
            if a["close"] is not None:
                a["close"] = round(a["close"], 0)

    activities.sort(key=lambda a: abs(a["nval"]), reverse=True)
    return {
        "broker": broker,
        "days": days,
        "start": start_s,
        "end": end_s,
        "scanned": len(tickers),
        "activities": activities,
        "errors": errors,
    }