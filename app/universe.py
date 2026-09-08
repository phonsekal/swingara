"""IDX universe & sector groups.

Sector assignment is a curated static map of the major/liquid IDX names (the
market-cap API provides codes + market cap but no sector). Anything not mapped
falls into "Lainnya". Groups are ordered for the UI.

Fallback saat arjum down / kuota habis memakai snapshot statis SEMUA saham IDX
(app/data/idx_universe.json, ~844 saham dengan market cap nyata dari TradingView)
alih-alih peta sektor yang cuma ~153 nama — jadi kelompok "top market cap" tetap
berisi 300 saham dan "kelompok ke-2" tetap berisi sisa pasar.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .arjum import ArjumClient, ArjumError

_DATA_DIR = Path(__file__).resolve().parent / "data"
_STATIC_UNIVERSE: Optional[list[dict]] = None


def static_universe_rows() -> list[dict]:
    """Full IDX snapshot (TradingView): code/name/market_cap, sorted cap desc.

    Lazy-loaded sekali; dipakai sebagai fallback saat arjum tidak tersedia.
    """
    global _STATIC_UNIVERSE
    if _STATIC_UNIVERSE is None:
        try:
            with open(_DATA_DIR / "idx_universe.json", encoding="utf-8") as f:
                data = json.load(f)
            stocks = data.get("stocks") or []
        except Exception as exc:
            print(f"static universe load gagal: {exc}", flush=True)
            stocks = []
        _STATIC_UNIVERSE = [
            {
                "code": s["code"],
                "name": s.get("name", ""),
                "market_cap": float(s.get("market_cap") or 0.0),
                "sector": group_of(s["code"]),
            }
            for s in stocks
            if s.get("code")
        ]
        _STATIC_UNIVERSE.sort(key=lambda r: r["market_cap"], reverse=True)
    return _STATIC_UNIVERSE

# (key, label) — order controls the UI dropdown
SECTORS: list[tuple[str, str]] = [
    ("Perbankan", "🏦 Perbankan"),
    ("Tambang", "⛏️ Tambang"),
    ("Energi", "🛢️ Energi"),
    ("Konsumen", "🛒 Konsumen & FMCG"),
    ("Farmasi & Kesehatan", "💊 Farmasi & Kesehatan"),
    ("Properti", "🏗️ Properti"),
    ("Konstruksi", "🚧 Konstruksi"),
    ("Infrastruktur", "🛣️ Infrastruktur"),
    ("Telekomunikasi", "📡 Telekomunikasi"),
    ("Transportasi", "🚌 Transportasi"),
    ("Teknologi & Media", "💻 Teknologi & Media"),
    ("Retail", "🏬 Retail"),
    ("Otomotif", "🚗 Otomotif"),
    ("Material", "🧱 Material & Kimia"),
    ("Perkebunan", "🌴 Perkebunan"),
    ("Lainnya", "📦 Lainnya"),
]

SECTOR_MAP: dict[str, str] = {
    # Perbankan
    "BBCA": "Perbankan", "BBRI": "Perbankan", "BMRI": "Perbankan", "BBNI": "Perbankan",
    "BBTN": "Perbankan", "BRIS": "Perbankan", "BNGA": "Perbankan", "BJBR": "Perbankan",
    "BJTM": "Perbankan", "MEGA": "Perbankan", "BDMN": "Perbankan", "NISP": "Perbankan",
    "PNBN": "Perbankan", "MAYA": "Perbankan", "AGRO": "Perbankan", "INPC": "Perbankan",
    "NOBU": "Perbankan", "SDRA": "Perbankan",
    # Tambang
    "ANTM": "Tambang", "TINS": "Tambang", "ADRO": "Tambang", "PTBA": "Tambang",
    "ITMG": "Tambang", "HRUM": "Tambang", "INCO": "Tambang", "MDKA": "Tambang",
    "BUMI": "Tambang", "BRMS": "Tambang", "DOID": "Tambang", "PSAB": "Tambang",
    "GTBO": "Tambang", "MBAP": "Tambang", "BESS": "Tambang", "NCKL": "Tambang",
    # Energi
    "PGAS": "Energi", "MEDC": "Energi", "ELSA": "Energi", "AKRA": "Energi",
    "ENRG": "Energi", "SUGI": "Energi", "SGER": "Energi", "RAJA": "Energi",
    "APEX": "Energi",
    # Konsumen
    "ICBP": "Konsumen", "INDF": "Konsumen", "UNVR": "Konsumen", "MYOR": "Konsumen",
    "ULTJ": "Konsumen", "DLTA": "Konsumen", "CAMP": "Konsumen", "GOOD": "Konsumen",
    "ROTI": "Konsumen", "STTP": "Konsumen", "CPIN": "Konsumen", "JPFA": "Konsumen",
    "MAIN": "Konsumen", "CEKA": "Konsumen", "SKBM": "Konsumen", "IKAN": "Konsumen",
    # Rokok (subgroup of konsumen but separate label not needed)
    "GGRM": "Konsumen", "HMSP": "Konsumen", "WIIM": "Konsumen",
    # Farmasi & Kesehatan
    "KLBF": "Farmasi & Kesehatan", "KAEF": "Farmasi & Kesehatan", "SIDO": "Farmasi & Kesehatan",
    "PYFA": "Farmasi & Kesehatan", "HEAL": "Farmasi & Kesehatan", "SILO": "Farmasi & Kesehatan",
    "MIKA": "Farmasi & Kesehatan", "PRDA": "Farmasi & Kesehatan", "RSGK": "Farmasi & Kesehatan",
    # Properti
    "SMRA": "Properti", "BSDE": "Properti", "CTRA": "Properti", "PWON": "Properti",
    "LPKR": "Properti", "ASRI": "Properti", "PPRO": "Properti", "DMAS": "Properti",
    "KIJA": "Properti", "BAPA": "Properti", "MTLA": "Properti", "JRPT": "Properti",
    # Konstruksi
    "WSKT": "Konstruksi", "WIKA": "Konstruksi", "PTPP": "Konstruksi", "ADHI": "Konstruksi",
    "TOTL": "Konstruksi", "ACST": "Konstruksi", "NRCA": "Konstruksi", "WEGE": "Konstruksi",
    "PTPW": "Konstruksi",
    # Infrastruktur
    "JSMR": "Infrastruktur", "TBIG": "Infrastruktur", "TOWR": "Infrastruktur",
    "MTEL": "Infrastruktur", "SUPR": "Infrastruktur", "CMNP": "Infrastruktur",
    # Telekomunikasi
    "TLKM": "Telekomunikasi", "ISAT": "Telekomunikasi", "EXCL": "Telekomunikasi",
    # Transportasi
    "GIAA": "Transportasi", "BIRD": "Transportasi", "ASSA": "Transportasi",
    "WEHA": "Transportasi", "CMPP": "Transportasi", "MIRA": "Transportasi",
    # Teknologi & Media
    "GOTO": "Teknologi & Media", "MTDL": "Teknologi & Media", "MNCN": "Teknologi & Media",
    "SCMA": "Teknologi & Media", "EMTK": "Teknologi & Media", "FILM": "Teknologi & Media",
    "BMTR": "Teknologi & Media", "LPPF": "Retail",  # corrected below
    # Retail
    "MAPI": "Retail", "ERAA": "Retail", "ACES": "Retail", "LPPF": "Retail",
    "RALS": "Retail", "AMRT": "Retail", "MIDI": "Retail", "CSIS": "Retail",
    # Otomotif
    "ASII": "Otomotif", "AUTO": "Otomotif", "SMSM": "Otomotif", "BRAM": "Otomotif",
    "INDX": "Otomotif", "NIPS": "Otomotif",
    # Material & Kimia
    "SMGR": "Material", "INTP": "Material", "WTON": "Material", "SMBR": "Material",
    "KRAS": "Material", "AMFG": "Material", "BRPT": "Material", "TPIA": "Material",
    "AKPI": "Material", "TKIM": "Material", "INKP": "Material", "FASW": "Material",
    "ALKA": "Material", "BTON": "Material", "BRNA": "Material", "EKAD": "Material",
    # Perkebunan
    "AALI": "Perkebunan", "LSIP": "Perkebunan", "TAPG": "Perkebunan", "SIMP": "Perkebunan",
    "SGRO": "Perkebunan", "DSNG": "Perkebunan", "BWPT": "Perkebunan", "GZCO": "Perkebunan",
    "SMAR": "Perkebunan",
}


def group_of(code: str) -> str:
    return SECTOR_MAP.get(code.upper(), "Lainnya")


def sector_tickers(sector: str) -> list[str]:
    return [c for c, s in SECTOR_MAP.items() if s == sector]


def all_mapped_tickers() -> list[str]:
    return all_mapped_tickers_by_market_cap_desc()


def all_mapped_tickers_by_market_cap_desc() -> list[str]:
    """Static candidate order: larger / more frequently traded names first.

    Keeps universe=mapped deterministic and offline while still surfacing the
    sa ham likuid / nilainya lebih besar lebih awal, yang bikin hasil scan
    lebih mudah diinterpretasi.
    """
    # Ideal: sort by real market cap. Since market cap requires the arjum
    # market_cap API, we keep this lightweight sentinel ordering as a fallback
    # that still biases toward names that tend to be bigger / more liquid.
    order = [
        # Banks
        "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "BNGA", "BJBR",
        "BJTM", "MEGA", "BDMN", "NISP", "PNBN", "MAYA", "AGRO", "INPC",
        "NOBU", "SDRA",
        # Mining
        "ANTM", "TINS", "ADRO", "PTBA", "ITMG", "HRUM", "INCO", "MDKA",
        "BUMI", "BRMS", "DOID", "PSAB", "GTBO", "MBAP", "BESS", "NCKL",
        # Energy
        "PGAS", "MEDC", "ELSA", "AKRA", "ENRG", "SUGI", "SGER", "RAJA",
        "APEX",
        # Consumer
        "ICBP", "INDF", "UNVR", "MYOR", "ULTJ", "DLTA", "CAMP", "GOOD",
        "ROTI", "STTP", "CPIN", "JPFA", "MAIN", "CEKA", "SKBM", "IKAN",
        "GGRM", "HMSP", "WIIM",
        # Health
        "KLBF", "KAEF", "SIDO", "PYFA", "HEAL", "SILO", "MIKA", "PRDA",
        "RSGK",
        # Property
        "SMRA", "BSDE", "CTRA", "PWON", "LPKR", "ASRI", "PPRO", "DMAS",
        "KIJA", "BAPA", "MTLA", "JRPT",
        # Construction
        "WSKT", "WIKA", "PTPP", "ADHI", "TOTL", "ACST", "NRCA", "WEGE",
        "PTPW",
        # Infrastructure
        "JSMR", "TBIG", "TOWR", "MTEL", "SUPR", "CMNP",
        # Telecom
        "TLKM", "ISAT", "EXCL",
        # Transport
        "GIAA", "BIRD", "ASSA", "WEHA", "CMPP", "MIRA",
        # Tech & media
        "GOTO", "MTDL", "MNCN", "SCMA", "EMTK", "FILM", "BMTR",
        # Retail
        "MAPI", "ERAA", "ACES", "LPPF", "RALS", "AMRT", "MIDI", "CSIS",
        # Auto
        "ASII", "AUTO", "SMSM", "BRAM", "INDX", "NIPS",
        # Material & chemical
        "SMGR", "INTP", "WTON", "SMBR", "KRAS", "AMFG", "BRPT", "TPIA",
        "AKPI", "TKIM", "INKP", "FASW", "ALKA", "BTON", "BRNA", "EKAD",
        # Plantation
        "AALI", "LSIP", "TAPG", "SIMP", "SGRO", "DSNG", "BWPT", "GZCO",
        "SMAR",
    ]
    desired = {c.upper() for c in order}
    mapped = set(SECTOR_MAP.keys())
    remaining = sorted(mapped - desired)
    return [c for c in order if c in mapped] + remaining


# ------------------------------------------------------------------- universe

UNIVERSE_TTL = 6 * 3600  # seconds
_universe_cache: dict = {"ts": 0.0, "rows": None}


async def fetch_universe(
    client: Optional[ArjumClient],
    min_market_cap_idr: float = 0.0,
    max_tickers: int = 300,
) -> list[dict]:
    """Full IDX list from /api/market-cap (cached 6h), sorted by market cap desc.

    Falls back to the full static IDX snapshot (app/data/idx_universe.json, ~844
    saham dengan market cap nyata) when the arjum client/key is unavailable —
    jadi "top market cap" tetap 300 saham dan "kelompok ke-2" tetap terisi meski
    kuota harian arjum habis.
    """
    now = time.monotonic()
    cache = _universe_cache
    if cache["rows"] is None or now - cache["ts"] > UNIVERSE_TTL:
        if client is None:
            cache["rows"] = []
            cache["ts"] = now
        else:
            try:
                first = await client.market_cap(page=1, per_page=50)
                total_pages = int(first.get("total_pages") or 1)
                pages = [first]
                for p in range(2, total_pages + 1):
                    pages.append(await client.market_cap(page=p, per_page=50))
                rows = [r for pg in pages for r in (pg.get("data") or [])]
            except ArjumError as exc:
                # arjum down / kuota habis -> jangan 500, fallback ke snapshot
                # statis SEMUA saham IDX (app/data/idx_universe.json, ~844)
                print(f"fetch_universe fallback ke snapshot statis: {exc}", flush=True)
                rows = []
            if rows:
                cache["rows"] = rows
                cache["ts"] = now

    rows = cache["rows"]
    if not rows:
        # no key / arjum error / kuota habis -> snapshot statis SEMUA saham IDX
        # (dengan market cap nyata), bukan cuma peta sektor ~153 nama.
        rows = static_universe_rows()

    out = []
    for r in rows:
        code = str(r.get("code", "")).upper()
        if not code:
            continue
        mc = float(r.get("market_cap") or 0.0)
        if mc >= min_market_cap_idr:
            out.append(
                {
                    "code": code,
                    "name": r.get("name", ""),
                    "market_cap": mc,
                    "sector": group_of(code),
                }
            )
    out.sort(key=lambda x: x["market_cap"], reverse=True)

    # top-up: kalau filter market cap menyisakan < max_tickers (mis. kuota habis
    # dan snapshot statis cuma punya ~294 saham cap>=3T), isi sisa slot dengan
    # kapitalisasi terbesar berikutnya supaya kelompok "top market cap" tetap 300.
    if len(out) < max_tickers and len(rows) > len(out):
        in_out = {x["code"] for x in out}
        rest = [
            {
                "code": str(r.get("code", "")).upper(),
                "name": r.get("name", ""),
                "market_cap": float(r.get("market_cap") or 0.0),
                "sector": group_of(str(r.get("code", "")).upper()),
            }
            for r in rows
            if str(r.get("code", "")).upper() and str(r.get("code", "")).upper() not in in_out
        ]
        rest.sort(key=lambda x: x["market_cap"], reverse=True)
        out.extend(rest[: max_tickers - len(out)])

    return out[:max_tickers]