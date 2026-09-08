"""Tests for the auto multi-method Layer A path (no method selection needed)."""
from __future__ import annotations

import asyncio

from app.models import ScanParams
from app.scanner import analyze_stock
from tests.test_scanner import CANDLES, FakeArjum, _params


def _tight_candles():
    """CANDLES with the last close nudged back toward the lower band (stays
    above EMA20 so the uptrend holds) so the wide method's 4% band-gap cap is
    satisfiable."""
    out = [dict(c) for c in CANDLES]
    out[-1] = {**out[-1], "open": 946.0, "high": 953.0, "low": 921.0, "close": 949.0}
    return out


def test_multi_method_returns_per_method_results():
    params = _params(multi_method=True)
    verdict = asyncio.run(analyze_stock("TEST", params, FakeArjum()))
    mr = verdict.method_results
    assert mr is not None
    assert len(mr) == 4  # strict_strong_buy, buy_quality_tighter, band_proximity_main, wide_candidate_pool
    names = [m["method"] for m in mr]
    assert names == ["strict_strong_buy", "buy_quality_tighter", "band_proximity_main", "wide_candidate_pool"]
    for m in mr:
        assert "passed" in m and "technicals" in m and "description" in m
        assert m["technicals"]["rsi14"] is not None
    # overall Layer A = any method passes
    assert (verdict.layers["a"]["status"] == "pass") == any(m["passed"] for m in mr)
    # wide pool is the loosest -> passes whenever any other method passes
    wide = next(m for m in mr if m["method"] == "wide_candidate_pool")
    if any(m["passed"] for m in mr):
        assert wide["passed"] is True


def test_multi_method_surfaces_detail_from_a_passing_method():
    params = _params(multi_method=True)
    verdict = asyncio.run(analyze_stock("TEST", params, FakeArjum()))
    mr = verdict.method_results or []
    passed = [m for m in mr if m["passed"]]
    if passed:
        # the surfaced Layer A detail is the first passing method's detail
        assert verdict.technicals["rsi14"] == passed[0]["technicals"]["rsi14"]


def test_layer_a_confirmation_gate_blocks_falling_knife():
    """require_close_above_ema5 / require_green_day gate the entry confirmation."""
    import numpy as np
    from app import technicals as ta
    from app.scanner import _layer_a

    candles = [dict(c) for c in CANDLES]
    params = _params(require_close_above_ema5=True, require_green_day=True)
    passed, detail = _layer_a(candles, params)
    assert "confirmation_ema5" in detail["checks"]
    assert "confirmation_green" in detail["checks"]
    # last CANDLES bar closes green above EMA5 -> both confirmations pass
    assert detail["checks"]["confirmation_ema5"] is True
    assert detail["checks"]["confirmation_green"] is True

    # craft a red bar that closes below EMA5 -> confirmation gates fail
    closes = np.asarray([c["close"] for c in candles], dtype=float)
    ema5_last = ta.ema(closes, 5)[-1]
    candles[-1] = {"open": 970.0, "high": 975.0, "low": 890.0, "close": 900.0, "volume": 55_000_000, "date": "fall"}
    assert 900.0 < ema5_last  # sanity: the crafted close is below EMA5
    _, detail2 = _layer_a(candles, params)
    assert detail2["checks"]["confirmation_green"] is False
    assert detail2["checks"]["confirmation_ema5"] is False


def test_multi_method_single_method_override_behavior_unchanged():
    # single-method pinning via layer_a_method should not produce method_results
    params = _params(layer_a_method="band_proximity_main", multi_method=False)
    verdict = asyncio.run(analyze_stock("TEST", params, FakeArjum()))
    assert verdict.method_results is None
    assert verdict.layers["a"]["status"] == "pass"


def test_multi_method_explanation_mentions_passing_methods():
    class DippingHistory(FakeArjum):
        async def history(self, code, limit=200, frame="daily"):
            return {"stock_code": code, "candles": _tight_candles()}

    params = _params(multi_method=True)
    verdict = asyncio.run(analyze_stock("TEST", params, DippingHistory()))
    assert verdict.explanation is not None
    texts = " ".join(p["text"] for p in verdict.explanation["points"])
    assert "metode" in texts
    assert "lolos:" in texts
    assert any(name in texts for name in ("band_proximity_main", "wide_candidate_pool"))
