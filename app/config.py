"""Runtime configuration from environment variables."""
from __future__ import annotations

import os


class Settings:
    arjum_base_url: str = os.getenv("ARJUM_BASE_URL", "https://stock.arjum.com")
    arjum_api_key: str = os.getenv("ARJUM_API_KEY", "").strip()

    default_watchlist: list[str] = [
        t.strip().upper()
        for t in os.getenv(
            "WATCHLIST",
            "BBRI,BMRI,TINS,BUMI,HRUM,BBCA,ASII,TLKM,ANTM,ADRO,PGAS,ICBP,INCO,PTBA,EXCL",
        ).split(",")
        if t.strip()
    ]

    request_timeout: float = float(os.getenv("ARJUM_TIMEOUT", "20"))
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "5"))
    cache_ttl: int = int(os.getenv("CACHE_TTL_SECONDS", "600"))


settings = Settings()