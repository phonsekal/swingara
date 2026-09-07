#!/usr/bin/env python3
"""Relaxed Layer-A scan across all mapped codes for comparison.

Same flow as scan_all_codes.py, but with looser liquidity / price filters so
you can compare how many additional candidates appear.

Usage:
  python3 scripts/scan_all_codes_relax.py > /tmp/scan_all_codes_relax.txt
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import ScanParams
from app.scanner import analyze_stock
from app.universe import all_mapped_tickers


async def run_all(*, params: ScanParams) -> list[dict]:
    tickers = all_mapped_tickers()
    results: list[dict] = []
    t0 = __import__("time").time()
    for i, code in enumerate(tickers, 1):
        try:
            v = await analyze_stock(code, params, None)
            results.append(v.model_dump() if hasattr(v, "model_dump") else v)
        except Exception as exc:  # noqa: BLE001
            results.append({"ticker": code, "verdict": "ERROR", "error": str(exc)})
        if i % 10 == 0 or i == len(tickers):
            elapsed = __import__("time").time() - t0
            print(
                f\"[{i:>4}/{len(tickers)}] {code:<8} {v.get('verdict') if isinstance(v, dict) else v.verdict}\",
                flush=True,
            )
    print(f\"\\nDone {len(tickers)} tickers in {__import__('time').time() - t0:.0f}s\", flush=True)
    return results


def summarize(results: list[dict]) -> dict:
    counts: dict[str, int] = {}
    passes: list[str] = []
    for r in results:
        v = r.get(\"verdict\") or \"UNKNOWN\"
        counts[v] = counts.get(v, 0) + 1
        layer_a_ok = (r.get(\"layers\") or {}).get(\"a\", {}).get(\"status\") == \"pass\"
        if layer_a_ok:
            passes.append(r.get(\"ticker\", \"\"))
    return {
        \"total\": len(results),
        \"by_verdict\": counts,
        \"layer_a_pass\": len(passes),
        \"layer_a_pass_codes\": passes,
    }


async def main() -> None:
    params = ScanParams(
        data_source=\"yfinance\",
        lookback_days=15,
        top_n_brokers=3,
        price_anchor_pct=3.0,
        min_liquidity_idr=1_000_000_000.0,
        min_price=100.0,
        max_price=None,
        min_history_days=60,
        rsi_max=70.0,
        pullback_pct=2.0,
        touch_tolerance_pct=1.0,
        touch_window_days=5,
    )

    results = await run_all(params=params)
    summary = summarize(results)
    out = {\"params\": params.model_dump(), \"summary\": summary, \"results\": results}
    pretty = json.dumps(out, ensure_ascii=False, indent=2)

    path = Path(\"/tmp/scan_all_codes_relax.json\")
    path.write_text(pretty, encoding=\"utf-8\")
    print(pretty)
    print(f\"\\nSaved to {path}\", flush=True)

    print(\"\\nSummary:\", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(\"\\nLayer A pass codes:\", flush=True)
    for code in summary.get(\"layer_a_pass_codes\", []):
        print(f\"  {code}\", flush=True)


if __name__ == \"__main__\":
    asyncio.run(main())
