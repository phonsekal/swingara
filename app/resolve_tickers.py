"""Resolves ticker universe selection for the scanner driver.

Supports four selection modes:
- custom: explicit tickers=... param
- sector: universe=sector&sector=<key>
- all: universe=all (top market-cap from market-cap API, capped)
- mapped: universe=mapped (all tickers in the static sector map, no API key needed)
- watchlist: default env WATCHLIST

Everything here is scheduler-safe as long as the caller supplies the right
universe-specific prerequisites. The static mapped list is deliberately fast
and offline so it can be used for a pure Layer-A scan without needing the
market-cap API.
"""
from __future__ import annotations

from app.universe import SECTORS, all_mapped_tickers, fetch_universe, group_of, sector_tickers
from app.models import ScanParams
from app.config import settings
from fastapi import HTTPException
from typing import Optional
from app.arjum import ArjumClient

__all__ = [
    "resolve_tickers",
    "SECTORS",
    "all_mapped_tickers",
    "sector_tickers",
    "group_of",
]


async def resolve_tickers(
    params: ScanParams, client: Optional[ArjumClient]
) -> tuple[list[str], str]:
    """Resolve tickers + human label from the universe/sector/tickers selection."""
    if params.tickers:
        seen: set[str] = set()
        out: list[str] = []
        for t in params.tickers:
            t = t.strip().upper().removesuffix(".JK")
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out, "custom"

    if params.universe == "sector" and params.sector:
        tickers = sector_tickers(params.sector)
        if not tickers:
            raise HTTPException(status_code=400, detail=f"Sektor tidak dikenal: {params.sector}")
        return tickers, f"sector:{params.sector}"

    if params.universe == "all":
        if client is None:
            raise HTTPException(status_code=400, detail="universe=all perlu client arjum (API key)")
        uni = await fetch_universe(
            client,
            min_market_cap_idr=params.min_market_cap_idr,
            max_tickers=params.max_tickers,
        )
        tickers = [u["code"] for u in uni]
        return tickers, f"all({len(tickers)})"

    if params.universe == "mapped":
        tickers = all_mapped_tickers()
        return tickers, "mapped"

    watchlist = [t.strip().upper() for t in settings.default_watchlist if t.strip()]
    if not watchlist:
        raise HTTPException(status_code=400, detail="watchlist kosong dan tidak ada universe terpilih")
    return watchlist, "watchlist"
