"""Tests for plain-language verdict explanations."""
from __future__ import annotations

import asyncio

from app.explain import explain_verdict
from app.models import ScanParams
from app.scanner import analyze_stock
from tests.test_scanner import FakeArjum, _params


def _explain(**overrides) -> dict:
    verdict = asyncio.run(analyze_stock("TEST", _params(**overrides), FakeArjum()))
    return verdict.explanation


def test_conviction_explanation_has_pass_points():
    ex = _explain()
    assert ex is not None
    assert ex["verdict"] == "MAXIMUM_CONVICTION_BUY"
    assert "kandidat BELI paling kuat" in ex["summary"]
    kinds = {p["kind"] for p in ex["points"]}
    assert "pass" in kinds
    assert any("tren jangka panjang masih NAIK" in p["text"] for p in ex["points"])
    assert any("AKUMULASI" in p["text"] for p in ex["points"])
    assert any("RETAIL MENJUAL" in p["text"] for p in ex["points"])


def test_rejected_explanation_mentions_failures():
    bad = [
        {"date": f"d{i}", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1e6}
        for i in range(200)
    ]

    class Flat(FakeArjum):
        async def history(self, code, limit=200, frame="daily"):
            return {"stock_code": code, "candles": bad}

    verdict = asyncio.run(analyze_stock("TEST", _params(), Flat()))
    ex = verdict.explanation
    assert ex["verdict"] == "REJECTED"
    assert any(p["kind"] == "fail" for p in ex["points"])
    assert "tidak direkomendasikan" in ex["summary"]


def test_glossary_present():
    from app.explain import GLOSSARY
    assert any(g["term"] == "RSI(14)" for g in GLOSSARY)
    assert len(GLOSSARY) >= 8