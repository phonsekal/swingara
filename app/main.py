"""FastAPI application for the IDX swing scanner (deployable on Vercel)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .alerts import format_alerts, send_telegram, send_webhook
from .arjum import ArjumClient, ArjumAuthError, ArjumError
from .backtest import backtest
from .budget import arjum_budget
from .config import settings
from .models import BacktestParams, ScanParams, ScanResponse, StockVerdict
from .resolve_method import default_method_params, list_methods
from .scanner import analyze_stock
from .resolve_tickers import resolve_tickers
from .universe import SECTORS, all_mapped_tickers, fetch_universe, group_of, sector_tickers, all_mapped_tickers_by_market_cap_desc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arjum = ArjumClient(
        settings.arjum_api_key,
        base_url=settings.arjum_base_url,
        timeout=settings.request_timeout,
        ttl=settings.cache_ttl,
    )
    yield
    await app.state.arjum.close()


app = FastAPI(
    title="IDX Swing Scanner API",
    description="Triple-layer swing scanner for IDX stocks: technicals (Layer A) + "
    "bandarmology broker accumulation with optional broker filter (Layer B) + "
    "anti-retail distribution audit (Layer C). Data via stock.arjum.com + yfinance.",
    version="1.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _client_for(request: Request) -> ArjumClient:
    """Per-request client so an X-API-Key header can override the env key."""
    key = (request.headers.get("X-API-Key") or settings.arjum_api_key).strip()
    return ArjumClient(
        key,
        base_url=settings.arjum_base_url,
        timeout=settings.request_timeout,
        ttl=settings.cache_ttl,
    )


def _resolve_key(request: Request) -> str:
    return (request.headers.get("X-API-Key") or settings.arjum_api_key).strip()


# ------------------------------------------------------------------- endpoints

@app.get("/", include_in_schema=False)
def index():
    page = STATIC_DIR / "index.html"
    if page.is_file():
        return FileResponse(str(page))
    return {"detail": "static/index.html not found"}


@app.get("/api/info")
def info():
    return {
        "name": "IDX Swing Scanner API",
        "version": app.version,
        "docs": "/docs",
        "endpoints": [
            "GET/POST /scan",
            "POST /scan/stream (NDJSON realtime)",
            "GET /api/universe",
            "GET /api/methods",
            "GET /api/methods/default",
            "GET /stocks/{code}",
            "GET /brokers/{code}",
            "GET /broker-accumulation/{code}",
            "GET /history/{code}",
            "POST /backtest",
            "GET/POST /api/alerts/run",
            "GET /health",
        ],
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "status": "healthy",
        "api_key_present": bool(settings.arjum_api_key),
        "arjum_usage": arjum_budget.usage(),
    }


@app.get("/api/universe")
async def universe_info(request: Request):
    """Sector groups + (optionally) the full market-cap universe."""
    client = _client_for(request)
    try:
        uni = await fetch_universe(client)
    finally:
        await client.close()
    groups = [
        {
            "key": key,
            "label": label,
            "count": len(sector_tickers(key)),
            "sample": sector_tickers(key)[:8],
        }
        for key, label in SECTORS
    ]
    return {
        "groups": groups,
        "universe_size": len(uni),
        "all_sample": [u["code"] for u in uni[:20]],
        "min_market_cap_idr": 3_000_000_000_000.0,
        "arjum_usage": arjum_budget.usage(),
    }


async def _resolve_tickers(
    params: ScanParams, client: Optional[ArjumClient]
) -> tuple[list[str], str]:
    """Resolve tickers + human label from the universe/sector/tickers selection."""
    return await resolve_tickers(params, client)


async def _run_scan(request: Request, params: ScanParams, *, use_default_method: bool = False) -> ScanResponse:
    client = _client_for(request)
    try:
        tickers, group = await _resolve_tickers(params, client)
    except Exception:
        await client.close()
        raise
    if not tickers:
        await client.close()
        raise HTTPException(status_code=400, detail="tickers kosong dan tidak ada universe terpilih")

    if use_default_method and params.layer_a_method:
        mp, desc = default_method_params(method=params.layer_a_method)
        if mp is None:
            await client.close()
            raise HTTPException(status_code=400, detail=desc or "method tidak diketahui")
        params = mp

    client_key = _resolve_key(request)
    sem = asyncio.Semaphore(settings.max_concurrency)

    async def one(code: str) -> StockVerdict:
        async with sem:
            return await analyze_stock(code, params, client)

    try:
        results = list(await asyncio.gather(*(one(c) for c in tickers)))
    finally:
        await client.close()

    counts: dict[str, int] = {}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    warnings: list[str] = []
    if not client_key:
        warnings.append(
            "ARJUM_API_KEY tidak diset — Layer B/C dilewati. Daftar key gratis di "
            "https://stock.arjum.com lalu set ARJUM_API_KEY (price history memakai yfinance)."
        )
    elif results and all(r.layers.get("b", {}).get("status") in ("unavailable", "skipped") for r in results):
        warnings.append("Tidak ada panggilan broker yang berhasil — cek validitas ARJUM_API_KEY.")

    return ScanResponse(
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        tickers_requested=tickers,
        api_key_present=bool(client_key),
        results=results,
        summary={"by_verdict": counts, "total": len(results)},
        warnings=warnings,
        arjum_usage=arjum_budget.usage(),
        group=group,
        method=params.layer_a_method if params.layer_a_method else None,
    )


@app.get("/scan")
async def scan_get(
    request: Request,
    tickers: str = Query("", description="Comma-separated, e.g. BBRI,BMRI,TINS"),
    brokers: str = Query("", description="OPTIONAL broker filter, e.g. SS or SS,YP (empty = any institutional broker)"),
    universe: str = Query("watchlist", description="watchlist | all | sector | mapped"),
    sector: Optional[str] = Query(None, description="Sector key when universe=sector (lihat /api/universe)"),
    min_market_cap_idr: float = 3_000_000_000_000.0,
    max_tickers: int = 300,
    lookback_days: int = 15,
    top_n_brokers: int = 3,
    flow: str = "all",
    price_anchor_pct: float = 3.0,
    min_liquidity_idr: float = 5_000_000_000.0,
    min_price: float = 100.0,
    max_price: Optional[float] = None,
    min_history_days: int = 60,
    rsi_max: float = 60.0,
    pullback_pct: float = 3.0,
    retail_brokers: str = "YP,CC,NI",
    data_source: str = "yfinance",
    anchor_mode: str = "vwap",
    include_seasonality: bool = False,
    include_news: bool = False,
    layer_a_method: Optional[str] = Query(None, description="Named Layer A method: strict_strong_buy | buy_quality_tighter | band_proximity_main | wide_candidate_pool"),
):
    params = ScanParams(
        tickers=[t for t in tickers.split(",") if t.strip()] if tickers else [],
        brokers=[b.strip().upper() for b in brokers.split(",") if b.strip()] if brokers else None,
        universe=universe,
        sector=sector,
        min_market_cap_idr=min_market_cap_idr,
        max_tickers=max_tickers,
        lookback_days=lookback_days,
        top_n_brokers=top_n_brokers,
        flow=flow,
        price_anchor_pct=price_anchor_pct,
        min_liquidity_idr=min_liquidity_idr,
        min_price=min_price,
        max_price=max_price,
        min_history_days=min_history_days,
        rsi_max=rsi_max,
        pullback_pct=pullback_pct,
        retail_brokers=[b.strip().upper() for b in retail_brokers.split(",") if b.strip()],
        data_source=data_source,
        anchor_mode=anchor_mode,
        include_seasonality=include_seasonality,
        include_news=include_news,
        layer_a_method=layer_a_method,
        band_gap_max_pct=3.0 if layer_a_method else 0.0,
    )
    return await _run_scan(request, params, use_default_method=True)


@app.get("/scan/sector-tickers")
async def scan_get_sector_tickers(
    sector: str = Query("", description="Sector key, lihat /api/universe"),
):
    if not sector:
        return {"groups": SECTORS}
    tickers = sector_tickers(sector)
    if not tickers:
        raise HTTPException(status_code=400, detail=f"Sektor tidak dikenal: {sector}")
    return {
        "sector": sector,
        "sector_label": next((label for key, label in SECTORS if key == sector), sector),
        "tickers": tickers,
        "count": len(tickers),
    }


@app.post("/scan")
async def scan_post(request: Request, params: ScanParams):
    return await _run_scan(request, params, use_default_method=True)


@app.get("/scan/stream/sector-tickers")
async def scan_get_stream_sector_tickers(
    sector: str = Query("", description="Sector key"),
):
    if not sector:
        return {"groups": SECTORS}
    tickers = sector_tickers(sector)
    if not tickers:
        raise HTTPException(status_code=400, detail=f"Sektor tidak dikenal: {sector}")
    return {
        "sector": sector,
        "sector_label": next((label for key, label in SECTORS if key == sector), sector),
        "tickers": tickers,
        "count": len(tickers),
    }


async def _scan_stream(request: Request, params: ScanParams):
    """NDJSON stream: meta -> one result line per ticker -> done. Powers the UI's
    realtime group-trend rendering."""
    stream_order: list[str] | None = None
    if params.universe == "mapped":
        stream_order = all_mapped_tickers_by_market_cap_desc()

    client = _client_for(request)
    try:
        tickers, group = await _resolve_tickers(params, client)
    except Exception:
        await client.close()
        raise
    if not tickers:
        await client.close()
        raise HTTPException(status_code=400, detail="tickers kosong dan tidak ada universe terpilih")

    sem = asyncio.Semaphore(settings.max_concurrency)

    async def one(code: str) -> StockVerdict:
        async with sem:
            return await analyze_stock(code, params, client)

    async def gen():
        _tickers = list(tickers)
        if stream_order is not None and set(_tickers).issubset(set(stream_order)):
            _tickers = [t for t in stream_order if t in set(_tickers)]
        yield json.dumps(
            {"type": "meta", "total": len(_tickers), "group": group, "tickers": _tickers, "params": params.model_dump(exclude={"tickers"})}
        ) + "\n"
        counts: dict[str, int] = {}
        try:
            for coro in asyncio.as_completed([one(c) for c in _tickers]):
                r = await coro
                counts[r.verdict] = counts.get(r.verdict, 0) + 1
                yield json.dumps({"type": "result", "ticker": r.ticker, "result": r.model_dump()}) + "\n"
        finally:
            await client.close()
        warnings: list[str] = []
        if not _resolve_key(request):
            warnings.append(
                "ARJUM_API_KEY tidak diset — Layer B/C dilewati. Daftar key gratis di "
                "https://stock.arjum.com lalu set ARJUM_API_KEY."
            )
        yield json.dumps(
            {
                "type": "done",
                "summary": {"by_verdict": counts, "total": len(tickers)},
                "arjum_usage": arjum_budget.usage(),
                "warnings": warnings,
                "group": group,
            }
        ) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/scan/stream")
async def scan_stream_post(request: Request, params: ScanParams):
    return await _scan_stream(request, params)


@app.get("/scan/stream")
async def scan_stream_get(
    request: Request,
    tickers: str = Query(""),
    brokers: str = Query(""),
    universe: str = Query("watchlist"),
    sector: Optional[str] = Query(None),
    lookback_days: int = 15,
    include_seasonality: bool = False,
    include_news: bool = False,
    data_source: str = "yfinance",
):
    params = ScanParams(
        tickers=[t for t in tickers.split(",") if t.strip()] if tickers else [],
        brokers=[b.strip().upper() for b in brokers.split(",") if b.strip()] if brokers else None,
        universe=universe,
        sector=sector,
        lookback_days=lookback_days,
        include_seasonality=include_seasonality,
        include_news=include_news,
        data_source=data_source,
    )
    return await _scan_stream(request, params)


@app.get("/stocks/{code}")
async def single_stock(
    request: Request,
    code: str,
    brokers: str = "",
    lookback_days: int = 15,
    include_seasonality: bool = True,
    include_news: bool = True,
):
    """Full single-stock analysis incl. seasonality, news & corp actions."""
    params = ScanParams(
        tickers=[code],
        brokers=[b.strip().upper() for b in brokers.split(",") if b.strip()] if brokers else None,
        lookback_days=lookback_days,
        include_seasonality=include_seasonality,
        include_news=include_news,
    )
    client = _client_for(request)
    try:
        (tickers, _) = await _resolve_tickers(params, client)
        result = await analyze_stock(tickers[0], params, client)
    finally:
        await client.close()
    result_dict = result.model_dump()
    result_dict["arjum_usage"] = arjum_budget.usage()
    return result_dict


def _broker_filter(rows: list[dict], brokers: Optional[set[str]], top_n: int) -> list[dict]:
    rows = sorted(rows, key=lambda r: float(r.get("nval") or 0.0), reverse=True)
    if brokers is not None:
        rows = [r for r in rows if str(r.get("broker_code", "")).upper() in brokers]
    return rows[:top_n]


@app.get("/brokers/{code}")
async def broker_summary(
    request: Request,
    code: str,
    brokers: str = Query("", description="OPTIONAL: only show these broker codes, e.g. SS"),
    top_n: int = Query(20, ge=1, le=200),
    flow: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    client = _client_for(request)
    end = end_date or date.today().isoformat()
    start = start_date or (date.today() - timedelta(days=24)).isoformat()
    try:
        raw = await client.broker_summary(code.upper().removesuffix(".JK"), start, end, broker_limit=200, flow=flow)
    except ArjumAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ArjumError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await client.close()

    rows = raw.get("brokers") or []
    wanted = {b.strip().upper() for b in brokers.split(",") if b.strip()} or None
    filtered = _broker_filter(rows, wanted, top_n)
    matched = bool(wanted) and any(
        str(r.get("broker_code", "")).upper() in wanted for r in rows
    )
    return {
        "stock_code": raw.get("stock_code", code.upper()),
        "broker_start": raw.get("broker_start"),
        "broker_end": raw.get("broker_end"),
        "latest_date": raw.get("latest_date"),
        "filter": {"brokers": sorted(wanted) if wanted else None, "top_n": top_n, "flow": flow},
        "matched": matched,
        "brokers": filtered,
        "arjum_usage": arjum_budget.usage(),
    }


@app.get("/broker-accumulation/{code}")
async def broker_accumulation(
    request: Request,
    code: str,
    brokers: str = Query("", description="OPTIONAL: e.g. SS,YP"),
    top: int = Query(3, ge=1, le=5),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    client = _client_for(request)
    end = end_date or date.today().isoformat()
    start = start_date or (date.today() - timedelta(days=24)).isoformat()
    try:
        raw = await client.broker_accumulation(
            code.upper().removesuffix(".JK"),
            start,
            end,
            top=top,
            brokers=[b.strip().upper() for b in brokers.split(",") if b.strip()] or None,
        )
    except ArjumAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ArjumError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await client.close()
    return {**raw, "arjum_usage": arjum_budget.usage()}


@app.get("/history/{code}")
async def history(request: Request, code: str, limit: int = Query(200, ge=20, le=500), frame: str = "daily"):
    client = _client_for(request)
    try:
        raw = await client.history(code.upper().removesuffix(".JK"), limit=limit, frame=frame)
    except ArjumAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ArjumError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await client.close()
    return {**raw, "arjum_usage": arjum_budget.usage()}


# ---------------------------------------------------------------------- backtest

@app.post("/backtest")
async def backtest_endpoint(request: Request, params: BacktestParams):
    client = _client_for(request)
    try:
        tickers, _ = await _resolve_tickers(params, client)
    except Exception:
        await client.close()
        raise
    if not tickers:
        await client.close()
        raise HTTPException(status_code=400, detail="tickers kosong")
    sem = asyncio.Semaphore(settings.max_concurrency)

    async def one(code: str) -> dict:
        async with sem:
            return await backtest(code, params, client)

    try:
        results = list(await asyncio.gather(*(one(c) for c in tickers)))
    finally:
        await client.close()
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "results": results,
        "combined": _combined_backtest_metrics(results),
        "arjum_usage": arjum_budget.usage(),
    }


# ------------------------------------------------------------------------ alerts


def _combined_backtest_metrics(results: list[dict]) -> dict:
    """Aggregate trade stats across all backtested tickers."""
    rets: list[float] = []
    holds: list[int] = []
    max_dds: list[float] = []
    for r in results:
        m = r.get("metrics") or {}
        for t in r.get("trades") or []:
            rets.append(t.get("return_pct", 0.0))
            holds.append(t.get("hold_days", 0))
        if m.get("max_drawdown_pct") is not None:
            max_dds.append(m["max_drawdown_pct"])
    if not rets:
        return {"n_trades": 0, "note": "tidak ada sinyal di periode ini"}
    wins = sum(1 for r in rets if r > 0)
    gross_win = sum(r for r in rets if r > 0)
    gross_loss = sum(abs(r) for r in rets if r < 0)
    return {
        "n_trades": len(rets),
        "win_rate_pct": round(wins / len(rets) * 100.0, 1),
        "avg_return_pct": round(sum(rets) / len(rets), 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "avg_hold_days": round(sum(holds) / len(holds), 1),
        "max_drawdown_pct": round(max(max_dds), 2) if max_dds else None,
        "note": "agregat semua ticker; return per trade (belum termasuk compounding)",
    }

@app.get("/api/alerts/run")
@app.post("/api/alerts/run")
async def run_alerts(request: Request):
    """Runs the configured alert scan and delivers via Telegram/webhook.

    GET is used by the Vercel cron job (09:30 UTC Mon-Fri = 16:30 WIB after close).
    If ALERT_SECRET is set, requests must send it via the `x-alert-secret` header.
    """
    secret = os.getenv("ALERT_SECRET", "").strip()
    if secret and request.headers.get("x-alert-secret") != secret:
        raise HTTPException(status_code=401, detail="x-alert-secret header salah")

    watchlist = [
        t.strip().upper() for t in os.getenv("ALERT_WATCHLIST", "").split(",") if t.strip()
    ] or settings.default_watchlist
    broker_filter = [
        b.strip().upper() for b in os.getenv("ALERT_BROKERS", "").split(",") if b.strip()
    ] or None
    lookback = int(os.getenv("ALERT_LOOKBACK_DAYS", "15"))

    params = ScanParams(tickers=watchlist, brokers=broker_filter, lookback_days=lookback)
    resp = await _run_scan(request, params, use_default_method=True)

    digest = format_alerts(resp.results, lookback)
    sent: dict = {}
    sent.update(await send_telegram(digest))
    sent.update(await send_webhook(digest))

    return {
        "generated_at": resp.generated_at,
        "summary": resp.summary,
        "warnings": resp.warnings,
        "arjum_usage": resp.arjum_usage,
        "sent": sent,
        "alert_preview": digest,
    }


@app.get("/api/methods")
def methods():
    return {
        "methods": list_methods(),
        "note": "These are the named Layer A methods exposed by the default scan path. Each method is a technical-screen philosophy, not a future win-rate guarantee.",
    }


@app.get("/api/methods/default")
def methods_default(request: Request):
    params = ScanParams(layer_a_method=None)
    return {
        "currently_no_default_method_assigned": True,
        "note": "The live default scan does not force a single method on every request yet. Use GET /scan?layer_a_method=band_proximity_main to pick one.",
    }
