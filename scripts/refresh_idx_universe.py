#!/usr/bin/env python3
"""Regenerate the static IDX universe snapshot (app/data/idx_universe.json).

Why
---
The scanner uses arjum /api/market-cap for the "top market cap" and "kelompok
ke-2" universe groups. When the daily arjum quota is exhausted (HTTP 429) the
API falls back to a static snapshot so the dropdowns and scans keep working.
This script refreshes that snapshot from the free TradingView IDX screener
(no arjum quota needed): ~844 stocks with real market caps (IDR).

Run:
  .venv/bin/python scripts/refresh_idx_universe.py

Output:
  app/data/idx_universe.json  ({generated_at, source, count, stocks:[...]})
"""
from __future__ import annotations

import datetime
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://scanner.tradingview.com/indonesia/scan"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "idx_universe.json"
COLUMNS = ["name", "close", "market_cap_basic", "sector", "description", "type"]


def fetch() -> list[dict]:
    body = {
        "symbols": {"tickers": [], "query": {"types": []}},
        "columns": COLUMNS,
        "range": [0, 2000],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.load(resp)

    rows = []
    for item in payload.get("data", []):
        d = item.get("d") or []
        if len(d) < len(COLUMNS):
            continue
        code, close, mcap, sector, desc, typ = d[0], d[1], d[2], d[3], d[4], d[5]
        if typ != "stock" or not code:
            continue
        rows.append(
            {
                "code": item["s"].split(":")[-1],
                "name": desc or code,
                "close": close,
                "market_cap": mcap,
                "tv_sector": sector,
            }
        )
    return rows


def main() -> int:
    print("Fetching IDX screener from TradingView ...")
    rows = fetch()
    if len(rows) < 500:
        print(f"Gagal: cuma {len(rows)} baris — batalkan, file lama dipertahankan.", file=sys.stderr)
        return 1

    # de-dup + sort by market cap desc
    seen: set[str] = set()
    uniq = []
    for r in rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        uniq.append(r)
    uniq.sort(key=lambda r: (r.get("market_cap") or 0), reverse=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "generated_at": datetime.date.today().isoformat(),
        "source": "TradingView screener (IDX), market_cap_basic dalam IDR",
        "count": len(uniq),
        "stocks": [
            {"code": r["code"], "name": r["name"], "market_cap": r["market_cap"], "tv_sector": r["tv_sector"]}
            for r in uniq
        ],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=0)
    print(f"OK: {len(uniq)} saham -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Top 5:", [r["code"] for r in uniq[:5]])
    return 0


if __name__ == "__main__":
    sys.exit(main())