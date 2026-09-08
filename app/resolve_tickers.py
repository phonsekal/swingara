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

    if params.universe in ("all", "all_extra"):
        if client is None:
            raise HTTPException(status_code=400, detail=f"universe={params.universe} perlu client arjum (API key)")
        # "all": top-N terbesar (filter market cap tetap); "all_extra": SEMUA
        # saham IDX di luar top-N — fetch universe penuh (cap >= 0) supaya
        # kelompok ke-2 benar-benar berisi sisa pasar, bukan sisa dari filter 3T.
        if params.universe == "all":
            uni = await fetch_universe(
                client,
                min_market_cap_idr=params.min_market_cap_idr,
                max_tickers=params.max_tickers + 5000,
            )
            tickers = [u["code"] for u in uni[: params.max_tickers]]
            return tickers, f"all({len(tickers)})"
        uni_full = await fetch_universe(
            client,
            min_market_cap_idr=0.0,
            max_tickers=params.max_tickers + 5000,
        )
        tickers = [u["code"] for u in uni_full[params.max_tickers:]]
        if not tickers:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Kelompok ke-2 kosong: universe penuh (963 saham) tidak tersedia — "
                    "kemungkinan kuota harian arjum habis. Coba lagi besok / tambah kuota."
                ),
            )
        return tickers, f"all_extra({len(tickers)})"

    if params.universe in ("mapped", "mapped_extra"):
        if params.universe == "mapped":
            return all_mapped_tickers(), "mapped"
        # sisa mapped universe yang tidak masuk kelompok top-N "all".
        if client is None:
            raise HTTPException(status_code=400, detail="universe=mapped_extra perlu client arjum (API key)")
        # Top-N ditentukan dari universe PENUH (bukan dari filter 3T) agar sisa
        # mapped yang dianggap "kelompok ke-2" konsisten dengan all_extra.
        uni = await fetch_universe(
            client,
            min_market_cap_idr=0.0,
            max_tickers=params.max_tickers + 5000,
        )
        top = {u["code"] for u in uni[: params.max_tickers]}
        tickers = [c for c in all_mapped_tickers() if c not in top]
        if not tickers:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Kelompok ke-2 mapped kosong: universe penuh tidak tersedia — "
                    "kemungkinan kuota harian arjum habis. Coba lagi besok / tambah kuota."
                ),
            )
        return tickers, f"mapped_extra({len(tickers)})"

    watchlist = [t.strip().upper() for t in settings.default_watchlist if t.strip()]
    if not watchlist:
        raise HTTPException(status_code=400, detail="watchlist kosong dan tidak ada universe terpilih")
    return watchlist, "watchlist"
