"""Tests for the IDX universe / sector mapping."""
from __future__ import annotations

import asyncio

from app.universe import SECTORS, all_mapped_tickers, group_of, sector_tickers


def test_known_sector_assignments():
    assert group_of("BBRI") == "Perbankan"
    assert group_of("BBCA") == "Perbankan"
    assert group_of("TINS") == "Tambang"
    assert group_of("ANTM") == "Tambang"
    assert group_of("PGAS") == "Energi"
    assert group_of("TLKM") == "Telekomunikasi"
    assert group_of("GOTO") == "Teknologi & Media"
    assert group_of("SMGR") == "Material"


def test_unknown_falls_back_to_lainnya():
    assert group_of("ZZZZ") == "Lainnya"


def test_sector_tickers_roundtrip():
    perbankan = sector_tickers("Perbankan")
    assert "BBRI" in perbankan
    assert "BBCA" in perbankan
    assert all(group_of(c) == "Perbankan" for c in perbankan)


def test_sectors_are_consistent():
    keys = {k for k, _ in SECTORS}
    assert "Lainnya" in keys
    for c in all_mapped_tickers():
        assert group_of(c) in keys


def test_fetch_universe_falls_back_to_static_map_without_key():
    async def go():
        uni = await _fetch()
        return uni

    # patch to avoid network: call with client=None (no key)
    from app.universe import fetch_universe

    async def _fetch():
        return await fetch_universe(None)

    uni = asyncio.run(go())
    assert len(uni) > 100
    assert all("code" in u and "sector" in u for u in uni)


def test_all_extra_returns_codes_beyond_top_n(monkeypatch):
    """universe=all_extra must contain the stocks NOT in the top-N group."""
    from app.models import ScanParams
    from app import resolve_tickers

    codes = [f"T{i:04d}" for i in range(1, 26)]  # 25 codes total

    async def fake_fetch_universe(client, min_market_cap_idr=0.0, max_tickers=300):
        return [{"code": c, "name": "", "market_cap": 1e12, "sector": "Lainnya"} for c in codes]

    monkeypatch.setattr(resolve_tickers, "fetch_universe", fake_fetch_universe)

    class DummyClient:
        pass

    async def go():
        params = ScanParams(universe="all_extra", max_tickers=10, min_market_cap_idr=0.0)
        return await resolve_tickers.resolve_tickers(params, DummyClient())

    tickers, label = asyncio.run(go())
    assert tickers == codes[10:]  # the 15 codes beyond the top-10 group
    assert label.startswith("all_extra")
    assert set(tickers).isdisjoint(set(codes[:10]))