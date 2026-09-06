# IDX Swing Scanner — FastAPI + Vercel

Web service + UI for swing trading Indonesian stocks (IDX): a triple-layer automated
scanner combining **technical filters** (Layer A), **bandarmology broker accumulation**
via the [stock.arjum.com](https://stock.arjum.com) (IDX Edge PRO) API (Layer B), and an
**anti-retail distribution audit** (Layer C). Strategy spec: [`perintah.md`](perintah.md).

## Features

- **Optional broker filter** — the core feature:
  - `brokers=SS` → only stocks where **SS** (Supra Sekuritas Indonesia) is inside the
    Top-N net buyers pass Layer B.
  - `brokers=SS,YP` → require *any one* of them; omit `brokers` → any non-retail
    (institutional) broker in the Top-N qualifies.
- **Verdicts:** `MAXIMUM_CONVICTION_BUY` (A+B+C), `STRONG_BUY` (A+B), `NEUTRAL_HOLD`
  (A pass, B fail), `WATCHLIST` (A pass, broker data unavailable), `REJECTED` (A fail).
- **Trading blueprint** per asset: entry zone, TP1 (+10%, 50% lot), TP2 (+20%), stop
  (fixed −6% or 2×ATR, tighter wins), suggested lots from a risk-per-trade budget.
- **Chase protection:** price must be within `price_anchor_pct`% of the lookback VWAP anchor.
- **🎨 Tailwind UI** at `/` — Scanner / Broker Flow / Backtest / Alerts tabs, with a
  realtime (streaming) group-trend panel while scanning.
- **🌐 Full-universe & sector scans** — scan **all ~963 IDX stocks** (market-cap
  prefiltered, capped) or a group: Perbankan, Tambang, Energi, Konsumen, Properti, etc.
- **📅 Seasonality** — per stock, which months historically rise/fall (multi-year
  yfinance history, **0 arjum quota**), shown as a 12-month bar chart.
- **📰 News & corp actions** — recent headlines + dividend/split history per stock
  (yfinance, 0 quota).
- **📈 Backtesting** — runs Layer A over multi-year history (yfinance only, **0 arjum
  quota**), reports trades, win rate, profit factor, max drawdown, equity curve.
- **🔔 Scheduled alerts** — Vercel cron runs the scan every weekday 16:30 WIB (09:30 UTC)
  and sends a digest to Telegram and/or a webhook.
- **💸 Quota-aware arjum usage (1000 req/day plan):**
  - Price history comes from **yfinance by default** (`data_source=yfinance`) — 0 arjum cost.
  - The arjum broker-summary call is made **only for tickers that pass Layer A**
    (technical filter kills most names first).
  - In-memory TTL cache + a best-effort daily budget guard (`ARJUM_DAILY_BUDGET`, default 900)
    that hard-stops requests when exhausted and reports usage in every response.

## Quickstart (local)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env   # fill ARJUM_API_KEY (register at https://stock.arjum.com)
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (UI) or /docs (Swagger).

## API

| Endpoint | Description |
|---|---|
| `GET/POST /scan` | Full scan. Query or JSON body (see params below). |
| `GET/POST /scan/stream` | Same scan as **NDJSON stream** (meta → results → done) for realtime UIs. |
| `GET /api/universe` | Sector groups + full market-cap universe. |
| `GET /stocks/{code}` | Single-stock full analysis — incl. seasonality, news & corp actions. |
| `GET /brokers/{code}` | Raw broker summary, optional `brokers`/`top_n`/`flow`/dates. |
| `GET /broker-accumulation/{code}` | Historical accumulation trend (`?brokers=SS`). |
| `GET /history/{code}` | OHLCV history proxy. |
| `POST /backtest` | Backtest Layer A on one or more tickers. |
| `GET/POST /api/alerts/run` | Run the alert scan now (GET = Vercel cron). |
| `GET /health` | Health + arjum quota usage. |

### Scan params (all optional)

`tickers`, `brokers`, `universe` (`watchlist`|`all`|`sector`), `sector` (key dari
`/api/universe`), `min_market_cap_idr` (3e12), `max_tickers` (300),
`lookback_days` (15), `top_n_brokers` (3), `flow` (`all|F|D`),
`price_anchor_pct` (3.0), `min_liquidity_idr` (5e9), `min_price` (100), `max_price`,
`min_history_days` (60), `rsi_max` (60, 0=off), `pullback_pct` (3.0, 0=off),
`retail_brokers` (`YP,CC,NI`), `retail_share_min` (0.5), `tp1_pct`/`tp2_pct`/`sl_pct`/
`atr_stop_mult`, `risk_per_trade_pct` (2.0), `portfolio_idr` (1e8),
`include_seasonality` (false), `include_news` (false),
`data_source` (`yfinance` default | `arjum`), `anchor_mode` (`vwap`|`avg_close`).
Backtest adds: `start_capital`, `fee_pct`, `max_hold_days`, `slippage_pct`, `history_years` (5).

Examples:

```bash
# only stocks where broker SS is accumulating in the Top-3
curl "https://<project>.vercel.app/scan?tickers=BBRI,BMRI,TINS,BUMI,HRUM&brokers=SS"

# scan an entire sector (Tambang) with seasonality
curl -X POST https://<project>.vercel.app/scan/stream \
  -H "Content-Type: application/json" \
  -d '{"universe": "sector", "sector": "Tambang", "include_seasonality": true}'

# inspect BBRI's broker flow filtered to SS
curl "https://<project>.vercel.app/brokers/BBRI?brokers=SS&top_n=10"

# backtest
curl -X POST https://<project>.vercel.app/backtest \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["TINS"], "lookback_days": 15, "max_hold_days": 30}'
```

## Environment variables

| Var | Purpose |
|---|---|
| `ARJUM_API_KEY` | **Required** for Layer B/C. Register at stock.arjum.com. |
| `ARJUM_BASE_URL` | Default `https://stock.arjum.com`. |
| `ARJUM_DAILY_BUDGET` | Best-effort daily request cap (default `900` of the 1000/day plan). |
| `WATCHLIST` | Default tickers for scans/alerts. |
| `MAX_CONCURRENCY`, `ARJUM_TIMEOUT`, `CACHE_TTL_SECONDS` | Performance tuning. |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Alert delivery via Telegram bot. |
| `ALERT_WEBHOOK_URL` | Generic webhook alert delivery (POSTs `{"text": ...}`). |
| `ALERT_WATCHLIST`, `ALERT_BROKERS`, `ALERT_LOOKBACK_DAYS` | Alert scan scope (defaults to `WATCHLIST`, no broker filter, 15 days). |
| `ALERT_SECRET` | If set, `/api/alerts/run` requires `x-alert-secret` header. |

## Deploy to Vercel

1. Push this repo to GitHub/GitLab and import it in Vercel.
   `vercel.json` routes everything to the `@vercel/python` function in `api/index.py`.
2. Add env vars in **Project → Settings → Environment Variables** (at least `ARJUM_API_KEY`).
3. Deploy. The UI is at `/`, docs at `/docs`.

The cron (weekdays 09:30 UTC = 16:30 WIB) is defined in `vercel.json`. Hobby plan
supports cron jobs; if yours doesn't, trigger `GET /api/alerts/run` from any external
scheduler (GitHub Actions, cron-job.org, etc.).

## Notes

- `buy_avg_anchor` is a **VWAP proxy**: the arjum API exposes broker buy value/frequency
  but not buy volume, so a true per-broker average price can't be computed. The anchor
  still does its job (chase protection).
- The daily budget counter is per warm instance (serverless is ephemeral) — a helpful
  guard, not a hard cross-instance quota.
- Your API key is a secret: keep it in `.env` locally (gitignored) and in Vercel env
  vars only — never commit it.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q   # offline: synthetic data + fake arjum client
```