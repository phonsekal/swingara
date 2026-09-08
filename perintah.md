# Role and Goal
You are an expert Quantitative Financial Engineer specializing in the Indonesian Stock Market (IDX), Bandarmology analysis, and serverless web application development. Build a complete, production-grade, deployable Python web service using **FastAPI** (deployed on **Vercel**) that combines an automated daily technical swing scanner with a 100% automated Broker Summary (Broksum) tracking engine powered by the `https://stock.arjum.com/` REST API.

**The broker filter MUST be optional and configurable.** Default behavior: the scanner accepts ANY non-retail (institutional) broker inside the Top N net buyers as Layer B confirmation. The user may optionally pin one or more specific broker codes (e.g. `SS` = Supra Sekuritas Indonesia) to require one of those brokers to be present — e.g. "only stocks where SS is accumulating" or any other broker code.

---

# 0. Architecture & Deployment

- **FastAPI** REST JSON API + a Tailwind CSS single-page UI served at `/`. Deployed on **Vercel** as a Python serverless function: `api/index.py` exposes the ASGI `app` object; `vercel.json` uses the `@vercel/python` builder and routes all traffic to it.
- Data sources (quota-aware — arjum plan is 1000 req/day):
  - Technical history: **`yfinance` by default** (`data_source=yfinance`, `.JK` suffix, 0 arjum cost); `GET https://stock.arjum.com/api/history/{code}` remains available via `data_source=arjum`.
  - Broker flow: `GET https://stock.arjum.com/api/broker-summary/{code}` (Top Buyers / Top Sellers / Net Value per broker) and `GET https://stock.arjum.com/api/broker-accumulation/{code}` (historical accumulation trend, supports a `brokers` comma-separated filter).
  - **Quota optimization:** the arjum broker call is made ONLY for tickers that already pass Layer A (technical filter kills most names first); in-memory TTL cache; a best-effort daily budget guard (`ARJUM_DAILY_BUDGET`, default 900) hard-stops requests when exhausted and reports usage in every response.
- **Authentication:** send `X-API-Key: <key>` on every arjum request. Read from `ARJUM_API_KEY` env var; a per-request `X-API-Key` header overrides it. If no key is present, the broker layers are marked `unavailable` and the scan degrades gracefully (technical layer still runs via yfinance).
- **Concurrency & resilience:** bounded `asyncio` concurrency (semaphore ≈ 5), request timeouts, one retry on 5xx/network errors.

# 1. REST API Surface

- `GET/POST /scan` — full triple-layer scan. Universe selection: `tickers` (manual list), `universe=watchlist` (env default), `universe=sector&sector=Perbankan` (group scan — see `/api/universe` for keys), or `universe=all` (full ~963-stock IDX list from `/api/market-cap`, prefiltered by `min_market_cap_idr` and capped by `max_tickers`). `GET/POST /scan/stream` returns the same scan as NDJSON (meta → per-ticker results → done) for realtime UIs with a live group-trend panel. Query params (POST = JSON body):
  - `tickers` (comma-separated; default: configurable watchlist, e.g. `BBRI,BMRI,TINS,BUMI,HRUM,BBCA,ASII,TLKM,ANTM,ADRO,PGAS,ICBP,INCO,PTBA,EXCL`)
  - `brokers` (**OPTIONAL**, comma-separated, e.g. `SS` or `SS,YP`): when provided, Layer B requires one of these brokers inside the Top N net buyers; when omitted, any non-retail broker inside Top N qualifies. **This is the optional broker filter.**
  - `lookback_days` (default 15), `top_n_brokers` (default 3), `flow` (`all`|`F`|`D`, default `all`), `price_anchor_pct` (default 3.0), `min_liquidity_idr` (default 5,000,000,000), `min_price` (default 50), `max_price` (optional), `min_history_days` (default 60), `rsi_max` (default 60, 0 disables), `pullback_pct` (default 3.0, 0 disables), `touch_tolerance_pct` (default 1.0), `retail_brokers` (default `YP,CC,NI`), `retail_share_min` (default 0.5), `tp1_pct` (10), `tp2_pct` (20), `sl_pct` (6), `atr_stop_mult` (2.0), `risk_per_trade_pct` (2.0), `portfolio_idr` (100,000,000), `data_source` (`arjum`|`yfinance`), `anchor_mode` (`vwap`|`avg_close`).
- `GET /stocks/{code}` — single-stock full analysis (same params) + **seasonality** (monthly up/down analysis from multi-year yfinance history, 0 quota) + **news** (recent headlines) + **corp actions** (dividends/splits) when `include_seasonality`/`include_news` are on (default true here).
- `GET /brokers/{code}` — raw broker summary for one ticker, with optional `brokers` / `top_n` / `flow` / `start_date` / `end_date` filters (the inspection endpoint: "show me only broker SS on BBCA").
- `GET /broker-accumulation/{code}` — historical accumulation trend proxy.
- `GET /history/{code}` — OHLCV history proxy.
- `POST /backtest` — backtest the Layer A strategy over `history_years` (default 5) of bars (yfinance only, 0 arjum quota): trade list, win rate, profit factor, max drawdown, equity curve.
- `GET/POST /api/alerts/run` — run the configured alert scan and deliver a digest to Telegram (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`) and/or webhook (`ALERT_WEBHOOK_URL`); `ALERT_SECRET` optional guard. Vercel cron in `vercel.json` fires it weekdays at 09:30 UTC (16:30 WIB).
- `GET /health` — health check + arjum quota usage.

# 2. Trading Strategy Rules (100% Automated Triple-Layer)

### Layer A: The Technical Filter (Swing Pullback Structure)
- **Trend regime:** validated uptrend where `Current Close > EMA 20` AND `EMA 20 > SMA 50`.
- **Discount-zone proximity:** `min(close, low)` is near or touching the Lower Bollinger Band (20 periods, 2 standard deviations) within `touch_tolerance_pct` (default 2%).
- **Multi-method default:** the live scan does NOT require picking a method — every ticker is evaluated under all four named Layer A methods (`strict_strong_buy`, `buy_quality_tighter`, `band_proximity_main`, `wide_candidate_pool`) and the per-method results are returned (`method_results`). Layer A passes if ANY method passes; Layer B/C still run once per ticker with base params.
- **Entry confirmation (backtest-backed):** every method requires the pullback to have STARTED turning before entry — `close > EMA5` AND a green day (`close > open`). Measured on 30–43 liquid IDX names over 5 years (2021–2026, TP5/10 + SL5 + ≤15-day hold, fee 0.25%/side + slippage), buying the bare band touch loses money (PF 0.7–0.9 across all tolerances), while adding the confirmation flips the pullback zone to positive. **Recalibrated Sep 2026** after a strong uptrend made the old ≥5% pullback gate produce ~0 candidates (median market pullback only ~3%): pullback lowered to 3.5–4.5% and band-touch tolerance widened to 2.5–4% while keeping the close-gap cap tight (4–6% — widening it to 6–8% loses money, PF 0.90–0.98). New ladder (5-yr backtest, 30 liquid names): strict (pull ≥ 4.5%, RSI ≤ 55, gap ≤ 4%, tol 2.5%) PF 1.25; quality (pull ≥ 4%, RSI ≤ 60, gap ≤ 5%, tol 3.5%) PF 1.17; main (pull ≥ 3.5%, RSI ≤ 65, gap ≤ 5%, tol 4%) PF 1.06; wide (pull ≥ 4%, RSI ≤ 70, gap ≤ 6%, tol 3.5%) PF 1.12.
- **Liquidity threshold:** 20-day average transaction value (`mean(close * volume)`) strictly greater than `min_liquidity_idr` (default IDR 5 Billion).
- **Quality guards (optimization over v1):**
  - Penny-stock filter: skip tickers below `min_price` (default Rp 50) — avoids untradeable micro-caps.
  - Minimum history: at least `min_history_days` (default 60) daily bars so indicators are stable.
  - RSI(14) < `rsi_max` (default 60): the pullback must not already be overbought.
  - Pullback depth: price retraced at least `pullback_pct` (default 3%) from the 20-day high — catches genuine pullbacks, skips vertical breakouts being chased.
  - ATR computed for volatility-aware stops (Layer 3).

### Layer B: The Automated Bandarmology Filter (stock.arjum.com API)
- **Data extraction:** query `broker-summary/{code}` with `start_date..end_date` covering the trailing `lookback_days` of trading (compute calendar range ≈ `lookback_days * 1.6` days back). Request enough `broker_limit` rows (≈ `max(top_n_brokers * 3, 20)`) so buyers and sellers can both be ranked. `flow` filters foreign/domestic/all.
- **Broker match (optional filter):**
  - If `brokers` is provided (e.g. `SS`): Broker Match = the ticker's Top N net buyers (by `nval`) contain at least one of the requested codes. If the requested broker is absent from Top N, Layer B fails — even if other brokers are accumulating.
  - If `brokers` is omitted: Broker Match = any broker inside Top N net buyers whose code is NOT in `retail_brokers` (institutional accumulation).
- **Anchor / chase protection:** `Current Close <= buy_avg_anchor * (1 + price_anchor_pct/100)` where `buy_avg_anchor` is the lookback **VWAP** (or average close in `anchor_mode=avg_close`) — a documented proxy for the broker's buy-average price, because the API exposes buy value/frequency but not buy volume. Prevents buying after price has already run more than ~3% above the accumulation zone.
- Report the matched broker code(s), their `bval/sval/nval`, the anchor price, and the anchor buffer.

### Layer C: The Anti-Retail Distribution Audit
- **Retail tracking:** from the same broker-summary payload, rank the Top `top_n_brokers` Net Sellers (`nval` ascending).
- **Verification:** pass when a prominent retail broker code (default `YP`, `CC`, `NI`) is present among the top net sellers AND retail's share of the total negative net value is ≥ `retail_share_min` (default 50%) — i.e. retail is *dominant* in the selling.

# 3. Dynamic Verdict Engine

- `MAXIMUM_CONVICTION_BUY` (green): Layer A + Layer B + Layer C all pass.
- `STRONG_BUY` (green-amber): Layer A + Layer B pass; Layer C fails/absent.
- `NEUTRAL_HOLD` (amber): Layer A passes but Layer B fails (requested broker absent, or price above the anchor zone).
- `WATCHLIST` (blue): Layer A passes but broker data is unavailable (e.g. no API key) — keep on radar, confirm bandarmology manually.
- `REJECTED` (gray): Layer A fails (any quality guard or technical condition).
- When `brokers` is set and the pinned broker is absent from the Top N → forced `NEUTRAL_HOLD`, never upgraded by other brokers.

# 4. Automated Trading Blueprint Output (per matched asset)

For every asset where Layer A passes:
- **Target entry range:** from the current close down to the Lower Bollinger Band line.
- **Take Profit 1:** `+tp1_pct`% (default +5%) for partial 50% lot locking.
- **Take Profit 2:** `+tp2_pct`% (default +10%) for full position liquidation.
- **Stop Loss:** `max(close * (1 - sl_pct/100), close - atr_stop_mult * ATR)` — the tighter of the fixed -5% capital protection and the volatility-adjusted (2×ATR) stop; structural exit note if close breaks the Lower Band.

**Backtest-driven defaults (5 tahun, 43 saham likuid — scripts/analyze_backtest.py):** the original +10/+20/−6 targets lose money (PF 0.79, win 33.6%). TP +5/+10 with SL −5% and ≤15-day holds turns the same signals positive (PF 1.11, win 48.9%, maxDD 5.6%) — these are the new defaults. Layer B/C (broker/retail) can't be backtested (no broker history) and act as a live confirmation filter on top.
- **Verified buy-average anchor** of the matched broker (VWAP proxy, clearly labeled).
- **Suggested position sizing:** `risk_per_trade_pct` of `portfolio_idr` divided by risk-per-share → lots of 100 shares, capped by portfolio capacity.

# 5. Persistence / Export

- All results returned as structured JSON (ready for any frontend).
- Include a per-verdict trading-plan block (Section 4) so clients can render/print it; provide an `export` convenience that dumps the matched set to `automated_trading_plan.txt` (same format as the v1 desktop tool, now via the API/CLI).

# 6. Universe & Sector Groups

- Sector assignment for the major/liquid IDX names lives in `app/universe.py` (curated map, ~250 tickers across Perbankan, Tambang, Energi, Konsumen, Farmasi & Kesehatan, Properti, Konstruksi, Infrastruktur, Telekomunikasi, Transportasi, Teknologi & Media, Retail, Otomotif, Material, Perkebunan, Lainnya). Unmapped tickers fall into "Lainnya".
- The full IDX listing (code, name, market cap, turnover) comes from `GET /api/market-cap` (20 pages, cached 6h, ~20 arjum calls once) — used for `universe=all` with a market-cap prefilter + ticker cap so scans fit the serverless 60s window.
- **Kelompok ke-2 (`universe=all_extra`):** returns the IDX names BEYOND the top-300 group (same market-cap filter, sliced after `max_tickers`), so the remainder of the market can be scanned as its own group. `universe=mapped_extra` does the same for the static mapped list.
- Seasonality is computed locally from multi-year yfinance history (0 quota), not the paid `/api/seasonal` endpoint.

# 7. Frontend UI (Tailwind CSS)

Single-page dark-themed UI served at `/` with four tabs:
- **Scanner** — universe/sector dropdown (Manual / Watchlist / Semua Saham / Semua Saham Kelompok ke-2 / per-sector), optional broker filter chips (SS/YP/CC/NI/BK/ZP), strategy params with **optimal defaults + reset button**, toggles for seasonality, news & weekly chart, verdict-colored result cards with Layer A/B/C breakdowns + per-method Layer A chips, trading blueprint, 12-month seasonality bar chart + **real 5-year monthly close chart**, news/corp-action panel (newest first), and a **weekly candlestick chart with Bollinger Band, MACD(12,26,9) & EMA5/EMA21 with golden-cross alert** — all rendered **realtime** from the NDJSON stream with a live group-trend panel (progress bar, verdict counts, avg RSI, avg pullback, Layer-A pass count, per-method pass summary).
- **Broker Flow** — per-ticker broker summary table (Buy/Sell/Net) with optional broker filter and MATCHED badge.
- **Backtest** — run the Layer A backtest and show metrics cards, equity curve SVG, and the trade list.
- **Alerts** — trigger the alert scan manually, show channel status and the message preview.

# 7. Scheduled Alerts

- `vercel.json` cron: `"30 9 * * 1-5"` (09:30 UTC = 16:30 WIB, after IDX close) → `GET /api/alerts/run`.
- Delivery: Telegram bot (env `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`) and/or generic webhook (`ALERT_WEBHOOK_URL`); both optional — without them the endpoint still returns the digest.
- Scope: `ALERT_WATCHLIST` (default `WATCHLIST`), optional `ALERT_BROKERS` filter, `ALERT_LOOKBACK_DAYS`.
- Hard-stop guard: daily arjum budget is shared with scans; alerts skip any ticker whose broker call would exceed the budget.

# 8. Backtesting

- Backtest the **Layer A** rules causally over historical bars (yfinance only — zero arjum quota): entry at next-bar open (with slippage), exits at TP1 (50%) / TP2 / stop / structural lower-band break / max-hold timeout; fees per side (default 0.25%). The backtest engine mirrors the live Layer A gate exactly, including the band-gap cap and the EMA5/green-day confirmation (`scripts/backtest_methods.py` reruns all four calibrated methods on cached 5-year history).
- Metrics: n trades, win rate, avg return, profit factor, max drawdown, avg hold days, total return; per-trade log + equity curve for charting.
- Layer B/C are market-regime checks (recent 10–20 days) and are intentionally excluded from long-window backtests — historical broker data is not available.