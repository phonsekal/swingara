"""Per-stock extras from yfinance (0 arjum quota): news & corporate actions."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .yf_lock import yf_lock

logger = logging.getLogger(__name__)


def _to_epoch_ms(ts) -> Optional[int]:
    try:
        return int(ts)
    except (TypeError, ValueError):
        return None


async def fetch_news(code: str, limit: int = 6, timeout: float = 12.0) -> Optional[list[dict]]:
    """Recent headlines via yfinance Ticker.get_news()."""
    try:
        import yfinance as yf
    except ImportError:
        return None

    def _get():
        with yf_lock:
            ticker = yf.Ticker(f"{code}.JK")
            raw = ticker.get_news() or []
        out = []
        for item in raw[: limit * 2]:
            content = item.get("content") or {}
            title = content.get("title")
            if not title:
                continue
            ts = _to_epoch_ms(content.get("pubDate"))
            date_str = (
                datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%d %b %Y")
                if ts
                else None
            )
            provider = ((content.get("provider") or {}).get("displayName")) or "—"
            url = ((content.get("canonicalUrl") or {}).get("url")) or item.get("link") or ""
            out.append(
                {
                    "title": title,
                    "publisher": provider,
                    "date": date_str,
                    "url": url,
                }
            )
            if len(out) >= limit:
                break
        return out

    try:
        return await asyncio.wait_for(asyncio.to_thread(_get), timeout=timeout)
    except Exception as exc:
        logger.warning("news fetch gagal untuk %s: %s", code, exc)
        return None


async def fetch_corp_actions(code: str, limit: int = 6, timeout: float = 10.0) -> Optional[list[dict]]:
    """Dividend & stock-split history via yfinance Ticker.get_actions()."""
    try:
        import yfinance as yf
    except ImportError:
        return None

    def _get():
        with yf_lock:
            ticker = yf.Ticker(f"{code}.JK")
            df = ticker.get_actions()
        if df is None or df.empty:
            return []
        cols = [str(c).split(",")[0].strip().lower() for c in df.columns]
        div_col = next((i for i, c in enumerate(cols) if "dividend" in c), None)
        split_col = next((i for i, c in enumerate(cols) if "split" in c), None)
        out = []
        for idx, row in df.tail(limit * 2).iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            div = float(row.iloc[div_col]) if div_col is not None else None
            split = float(row.iloc[split_col]) if split_col is not None else None
            if (div and div > 0) or (split and abs(split) > 0.001):
                out.append(
                    {
                        "date": date_str,
                        "dividend": round(div, 2) if div else None,
                        "split": round(split, 4) if split else None,
                        "kind": "DIVIDEN" if div else ("STOCK SPLIT" if split else ""),
                    }
                )
            if len(out) >= limit:
                break
        return out

    try:
        return await asyncio.wait_for(asyncio.to_thread(_get), timeout=timeout)
    except Exception as exc:
        logger.warning("corp actions fetch gagal untuk %s: %s", code, exc)
        return None