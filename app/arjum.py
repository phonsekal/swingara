"""Async client for the stock.arjum.com (IDX Edge PRO) REST API.

Endpoints (verified against the live site):
  GET /api/history/{code}?limit=..&frame=daily        -> {"candles": [{date, open, high, low, close, volume}]}
  GET /api/broker-summary/{code}?start_date=..&end_date=..&broker_limit=..&flow=..
      -> {"brokers": [{broker_code, broker_name, bval, sval, nval, nvol, bfrq, sfrq}]}
  GET /api/broker-accumulation/{code}?start_date=..&end_date=..&top=3&brokers=SS,YP
      -> {"top_buyers": [{broker_code, broker_name, net_val}], "series": [{date, accum_val}]}

Auth: X-API-Key header (required by the API).
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from .budget import arjum_budget


class ArjumError(Exception):
    """Generic API error (network, HTTP 4xx/5xx)."""


class ArjumAuthError(ArjumError):
    """HTTP 401/403 -> missing or invalid API key."""


class ArjumClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://stock.arjum.com",
        timeout: float = 20.0,
        ttl: int = 600,
        max_retries: int = 1,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._ttl = ttl
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: dict[str, tuple[float, Any]] = {}

    # ---------------------------------------------------------------- public

    async def history(self, code: str, limit: int = 200, frame: str = "daily") -> dict:
        return await self._get(f"/api/history/{code}", {"limit": limit, "frame": frame})

    async def broker_summary(
        self,
        code: str,
        start_date: str,
        end_date: str,
        broker_limit: int = 20,
        flow: str = "all",
        net: bool = False,
    ) -> dict:
        return await self._get(
            f"/api/broker-summary/{code}",
            {
                "start_date": start_date,
                "end_date": end_date,
                "broker_limit": broker_limit,
                "flow": flow,
                "net": net,
            },
        )

    async def broker_accumulation(
        self,
        code: str,
        start_date: str,
        end_date: str,
        top: int = 3,
        brokers: Optional[list[str]] = None,
    ) -> dict:
        params: dict[str, Any] = {"start_date": start_date, "end_date": end_date, "top": top}
        if brokers:
            params["brokers"] = ",".join(brokers)
        return await self._get(f"/api/broker-accumulation/{code}", params)

    async def market_cap(self, page: int = 1, per_page: int = 50) -> dict:
        """Full IDX listing (963 stocks) — code, name, close, market cap, turnover."""
        return await self._get("/api/market-cap", {"page": page, "per_page": per_page})

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # --------------------------------------------------------------- private

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        cache_key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
        now = time.monotonic()
        hit = self._cache.get(cache_key)
        if hit is not None and now - hit[0] < self._ttl:
            return hit[1]

        if not arjum_budget.spend():
            raise ArjumError(
                f"Budget harian arjum habis ({arjum_budget.budget} req). "
                "Tunggu reset harian atau naikkan ARJUM_DAILY_BUDGET."
            )

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)

        last_err: Optional[ArjumError] = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.get(
                    f"{self._base}{path}", params=params, headers=self._headers()
                )
            except httpx.HTTPError as exc:
                last_err = ArjumError(f"network error: {exc}")
                continue

            if resp.status_code in (401, 403):
                raise ArjumAuthError(
                    "Autentikasi arjum gagal: set ARJUM_API_KEY (atau header X-API-Key) "
                    "dengan API key yang valid dari https://stock.arjum.com"
                )
            if resp.status_code >= 400:
                last_err = ArjumError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                continue

            data = resp.json()
            self._cache[cache_key] = (now, data)
            return data

        raise last_err or ArjumError("unknown error")

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers