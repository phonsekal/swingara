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


def test_static_universe_snapshot_is_complete():
    """Snapshot statis berisi SEMUA saham IDX (~844) dengan market cap nyata —
    bukan cuma peta sektor ~153 nama."""
    from app.universe import static_universe_rows

    rows = static_universe_rows()
    assert len(rows) > 800
    assert len({r["code"] for r in rows}) == len(rows)
    assert rows[0]["code"] == "BBCA"  # kapitalisasi terbesar
    assert all(r["market_cap"] > 0 for r in rows[:100])


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


def test_fetch_universe_fallback_fills_full_top_n():
    """Saat kuota habis, fallback snapshot statis tetap mengisi 300 saham
    (top-up dari kapitalisasi berikutnya walau filter 3T cuma ~294)."""
    from app.universe import fetch_universe

    async def go():
        return await fetch_universe(None, min_market_cap_idr=3_000_000_000_000.0, max_tickers=300)

    uni = asyncio.run(go())
    assert len(uni) == 300
    assert uni[0]["code"] == "BBCA"
    assert all("code" in u and "sector" in u for u in uni)


def test_fetch_universe_falls_back_when_arjum_errors(monkeypatch):
    """Quota habis / arjum down must NOT 500 — fallback ke peta statis."""
    from app.arjum import ArjumError
    from app.universe import fetch_universe

    class BoomClient:
        async def market_cap(self, page: int = 1, per_page: int = 50) -> dict:
            raise ArjumError("HTTP 429: kuota habis")

        async def close(self) -> None:
            pass

    async def go():
        return await fetch_universe(BoomClient(), min_market_cap_idr=0.0, max_tickers=50)

    uni = asyncio.run(go())
    assert len(uni) == 50  # static map fallback, no exception
    assert all("code" in u and "sector" in u for u in uni)


def test_universe_endpoint_returns_groups_when_arjum_down(monkeypatch):
    """GET /api/universe must always return sector groups (dropdown UI)."""
    from app.arjum import ArjumError
    from app import main as main_mod

    async def boom(client):
        raise ArjumError("HTTP 429: kuota habis")

    monkeypatch.setattr(main_mod, "fetch_universe", boom)

    from starlette.testclient import TestClient

    with TestClient(main_mod.app) as c:
        r = c.get("/api/universe")
    assert r.status_code == 200
    j = r.json()
    assert len(j["groups"]) == len(SECTORS)
    assert any(g["key"] == "Perbankan" for g in j["groups"])


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


def test_all_extra_works_with_static_fallback():
    """Kelompok ke-2 TIDAK lagi kosong saat kuota arjum habis — fallback snapshot
    statis berisi 844 saham, jadi sisa setelah top-300 = ~544 saham."""
    from app.arjum import ArjumError
    from app.models import ScanParams
    from app import resolve_tickers

    class BoomClient:
        async def market_cap(self, page: int = 1, per_page: int = 50) -> dict:
            raise ArjumError("HTTP 429: kuota habis")

        async def close(self) -> None:
            pass

    async def go():
        params = ScanParams(universe="all_extra", max_tickers=300, min_market_cap_idr=0.0)
        return await resolve_tickers.resolve_tickers(params, BoomClient())

    tickers, label = asyncio.run(go())
    assert len(tickers) > 500  # 844 - 300 = 544
    assert label.startswith("all_extra")
    assert "BBCA" not in tickers  # BBCA masuk top-300, bukan kelompok ke-2


def test_all_extra_empty_raises_clear_503(monkeypatch):
    """Kelompok ke-2 kosong (fallback statis saat kuota habis) -> 503 jelas, bukan 400 membingungkan."""
    from app.models import ScanParams
    from app import resolve_tickers
    from fastapi import HTTPException

    async def fake_fetch_universe(client, min_market_cap_idr=0.0, max_tickers=300):
        # fallback statis: hanya 50 nama < max_tickers -> slice [300:] kosong
        return [{"code": f"T{i:04d}", "name": "", "market_cap": 0.0, "sector": "Lainnya"} for i in range(1, 51)]

    monkeypatch.setattr(resolve_tickers, "fetch_universe", fake_fetch_universe)

    async def go():
        params = ScanParams(universe="all_extra", max_tickers=300, min_market_cap_idr=0.0)
        return await resolve_tickers.resolve_tickers(params, object())

    try:
        asyncio.run(go())
        assert False, "harusnya raise HTTPException 503"
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "kuota" in exc.detail.lower()