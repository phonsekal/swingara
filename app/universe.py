"""IDX universe & sector groups.

Sector assignment is a curated static map of the major/liquid IDX names (the
market-cap API provides codes + market cap but no sector). Anything not mapped
falls into "Lainnya". Groups are ordered for the UI.
"""
from __future__ import annotations

import time
from typing import Optional

from .arjum import ArjumClient

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
    return sorted(SECTOR_MAP.keys())


# ------------------------------------------------------------------- universe

UNIVERSE_TTL = 6 * 3600  # seconds
_universe_cache: dict = {"ts": 0.0, "rows": None}


async def fetch_universe(
    client: Optional[ArjumClient],
    min_market_cap_idr: float = 0.0,
    max_tickers: int = 300,
) -> list[dict]:
    """Full IDX list from /api/market-cap (cached 6h), sorted by market cap desc.

    Falls back to the static sector map when the arjum client/key is unavailable.
    """
    now = time.monotonic()
    cache = _universe_cache
    if cache["rows"] is None or now - cache["ts"] > UNIVERSE_TTL:
        if client is None:
            cache["rows"] = []
            cache["ts"] = now
        else:
            first = await client.market_cap(page=1, per_page=50)
            total_pages = int(first.get("total_pages") or 1)
            pages = [first]
            for p in range(2, total_pages + 1):
                pages.append(await client.market_cap(page=p, per_page=50))
            rows = [r for pg in pages for r in (pg.get("data") or [])]
            if rows:
                cache["rows"] = rows
                cache["ts"] = now

    rows = cache["rows"]
    if not rows:
        # no key / empty -> static map only
        return [
            {"code": c, "name": "", "market_cap": 0.0, "sector": group_of(c)}
            for c in all_mapped_tickers()
        ][:max_tickers]

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
    return out[:max_tickers]