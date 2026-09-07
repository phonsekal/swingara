"""Pydantic request/response schemas."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScanParams(BaseModel):
    """Everything tunable in the triple-layer scan."""

    model_config = ConfigDict(extra="ignore")

    tickers: list[str] = Field(
        default_factory=list,
        description="Stock codes without .JK suffix. Empty = default watchlist.",
    )
    # --- optional broker filter (the core feature) ---
    brokers: Optional[list[str]] = Field(
        default=None,
        description="Optional broker filter, e.g. ['SS']. When set, Layer B requires "
        "one of these brokers in the Top N net buyers. When None, any non-retail "
        "broker in Top N qualifies.",
    )
    lookback_days: int = 15
    top_n_brokers: int = 3
    flow: Literal["all", "F", "D"] = "all"
    price_anchor_pct: float = 3.0

    # --- Layer A ---
    min_liquidity_idr: float = 5_000_000_000.0
    min_price: float = 50.0
    max_price: Optional[float] = None
    min_history_days: int = 60
    ema_period: int = 20
    sma_period: int = 50
    bb_period: int = 20
    bb_std: float = 2.0
    touch_tolerance_pct: float = 1.0
    rsi_max: float = 60.0  # 0 disables
    pullback_pct: float = 3.0  # 0 disables

    # --- Layer C ---
    retail_brokers: list[str] = Field(default_factory=lambda: ["YP", "CC", "NI"])
    retail_share_min: float = 0.5

    # --- Blueprint (defaults dari backtest 5 tahun, lihat scripts/tune.py) ---
    # Target +10/+20% terlalu jauh: PF 0.76 (rugi). TP 5/10 + SL 5 + hold 15 hari
    # menghasilkan PF 1.11 & win rate 48.9% pada sampel yang sama.
    tp1_pct: float = 5.0
    tp2_pct: float = 10.0
    sl_pct: float = 5.0
    atr_stop_mult: float = 2.0
    risk_per_trade_pct: float = 2.0
    portfolio_idr: float = 100_000_000.0

    # --- Universe selection ---
    universe: Literal["watchlist", "all", "sector"] = "watchlist"
    sector: Optional[str] = None  # used when universe == "sector"
    min_market_cap_idr: float = 3_000_000_000_000.0  # used when universe == "all"
    max_tickers: int = 300  # cap for universe == "all" (serverless 60s window)

    # --- Extras ---
    include_seasonality: bool = False  # monthly up/down analysis (multi-year yfinance history)
    include_news: bool = False  # recent news + corp actions per stock (yfinance)

    # --- Data source ---
    # yfinance-first: price history costs 0 arjum quota; arjum is used only for
    # the broker-summary (bandarmology) layer.
    data_source: Literal["arjum", "yfinance"] = "yfinance"
    anchor_mode: Literal["vwap", "avg_close"] = "vwap"


class StockVerdict(BaseModel):
    """Per-ticker scan result."""

    model_config = ConfigDict(extra="allow")

    ticker: str
    verdict: str
    layers: dict  # a / b / c -> {status, details}
    reasons: list[str] = Field(default_factory=list)
    technicals: dict = Field(default_factory=dict)
    broker_flow: Optional[dict] = None
    plan: Optional[dict] = None
    error: Optional[str] = None
    # extras (filled when requested): seasonality / news / corp_actions
    seasonality: Optional[dict] = None
    news: Optional[list] = None
    corp_actions: Optional[list] = None
    # plain-language explanation of the verdict (always filled)
    explanation: Optional[dict] = None


class ScanResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: str
    tickers_requested: list[str]
    api_key_present: bool
    results: list[StockVerdict]
    summary: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    arjum_usage: Optional[dict] = None


class BacktestParams(ScanParams):
    """Scan strategy params + backtest-specific settings."""

    start_capital: float = 100_000_000.0
    fee_pct: float = 0.25  # round-trip fee per side (%)
    max_hold_days: int = 30
    slippage_pct: float = 0.1
    history_years: int = 5  # multi-year window for a meaningful sample