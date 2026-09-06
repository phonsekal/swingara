"""Scheduled-alert delivery for the daily scan.

Channels (config via env):
  - Telegram bot: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  - Generic webhook: ALERT_WEBHOOK_URL (POSTs {"text": ...})
If neither is configured, the endpoint still runs the scan and returns the digest.
"""
from __future__ import annotations

import os

import httpx

VERDICT_EMOJI = {
    "MAXIMUM_CONVICTION_BUY": "🟢",
    "STRONG_BUY": "🟩",
    "NEUTRAL_HOLD": "🟡",
    "WATCHLIST": "🔵",
    "REJECTED": "⚪",
}


def format_alerts(results: list, lookback_days: int) -> str:
    """Compact HTML digest for Telegram/webhook."""
    lines = [f"<b>🔔 IDX Swing Scanner — Alert Harian</b> (lookback {lookback_days} hari)", ""]
    wanted = ["MAXIMUM_CONVICTION_BUY", "STRONG_BUY", "WATCHLIST"]
    shown = 0
    for verdict in wanted:
        group = [r for r in results if r.verdict == verdict]
        if not group:
            continue
        lines.append(f"<b>{VERDICT_EMOJI[verdict]} {verdict}</b> ({len(group)})")
        for r in group:
            p = r.plan or {}
            zone = p.get("entry_zone") or {}
            anchor = p.get("buy_avg_anchor")
            lines.append(
                f"  • {r.ticker} — {r.technicals.get('close', '-')} | "
                f"entry {zone.get('from', '-')}–{zone.get('to', '-')} | "
                f"TP {p.get('tp1_price', '-')}/{p.get('tp2_price', '-')} | "
                f"SL {p.get('stop_loss', '-')}"
                + (f" | anchor {round(anchor):,}" if anchor else "")
            )
            shown += 1
    if shown == 0:
        lines.append("Tidak ada sinyal layak hari ini. 🙏")
    lines.append("")
    lines.append("— dikirim otomatis oleh IDX Swing Scanner")
    return "\n".join(lines)


async def send_telegram(text: str) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"telegram": "skipped: set TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        if resp.status_code == 200:
            return {"telegram": "sent"}
        return {"telegram": f"failed HTTP {resp.status_code}: {resp.text[:120]}"}
    except httpx.HTTPError as exc:
        return {"telegram": f"error: {exc}"}


async def send_webhook(text: str) -> dict:
    url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not url:
        return {"webhook": "skipped: set ALERT_WEBHOOK_URL"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={"text": text})
        if resp.status_code < 400:
            return {"webhook": "sent"}
        return {"webhook": f"failed HTTP {resp.status_code}: {resp.text[:120]}"}
    except httpx.HTTPError as exc:
        return {"webhook": f"error: {exc}"}