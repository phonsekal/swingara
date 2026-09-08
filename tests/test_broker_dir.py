"""Tests for the broker directory (smart money vs retail) + broker activity scan."""
from __future__ import annotations

import asyncio

import pytest

from unittest import mock

from app.arjum import ArjumError
from app.broker_dir import (
    RETAIL_CODES,
    SMART_MONEY_CODES,
    broker_info,
    directory,
)
from app.broker_activity import broker_activity


def _run_activity(*args):
    """Run broker_activity with the yfinance batch-price call stubbed out."""
    with mock.patch("app.broker_activity._batch_close_prices", return_value={}):
        return asyncio.run(broker_activity(*args))


def test_directory_has_expected_brokers():
    d = directory()
    codes = {b["code"] for b in d}
    assert len(d) >= 80
    # kode yang dipakai di UI & chips harus ada
    for code in ("SS", "YP", "CC", "NI", "BK", "ZP", "XC", "XL", "DH", "EP"):
        assert code in codes, f"{code} tidak ada di direktori"


def test_directory_fields_complete():
    for b in directory():
        assert b["code"] and b["name"]
        assert b["category"] in {"foreign", "bumn", "conglomerate", "online_retail", "local"}
        assert b["tags"], f"{b['code']} tanpa tags"
        assert b["group"]
        assert isinstance(b["issuers"], list)


def test_smart_money_and_retail_partition():
    d = directory()
    assert SMART_MONEY_CODES and RETAIL_CODES
    assert not (SMART_MONEY_CODES & RETAIL_CODES)
    assert len(SMART_MONEY_CODES) + len(RETAIL_CODES) == len(d)


def test_broker_info_unknown():
    assert broker_info("ZZ") is None


def test_broker_info_known():
    info = broker_info("AK")
    assert info is not None
    assert info["name"] == "UBS Sekuritas Indonesia"
    assert "smart_money" in info["tags"]
    assert info["group"] == "UBS Group (Swiss)"


def test_affiliation_issuers_exist_for_conglomerates():
    for code in ("DH", "EP", "CD", "SQ", "GR"):
        info = broker_info(code)
        assert info is not None and info["issuers"], f"{code} seharusnya punya daftar emiten afiliasi"


# ---------------------------------------------------------------- activity


class _FakeClient:
    """Minimal ArjumClient stand-in returning canned broker summaries."""

    def __init__(self, summaries: dict[str, dict]):
        self._summaries = summaries
        self.calls: list[str] = []

    async def broker_summary(self, code, start_date, end_date, broker_limit=20, flow="all", net=False):
        self.calls.append(code)
        if code not in self._summaries:
            raise ArjumError(f"no data for {code}")
        return self._summaries[code]


def _summary(*rows):
    return {"brokers": [dict(r) for r in rows], "broker_start": "2026-09-01", "broker_end": "2026-09-07"}


def test_broker_activity_filters_one_broker():
    client = _FakeClient(
        {
            "BBRI": _summary(
                {"broker_code": "SS", "broker_name": "Supra", "bval": 5e9, "sval": 1e9, "nval": 4e9, "nvol": 100, "bfrq": 5, "sfrq": 2},
                {"broker_code": "YP", "broker_name": "Mirae", "bval": 1e9, "sval": 3e9, "nval": -2e9, "nvol": -50, "bfrq": 1, "sfrq": 4},
            ),
            "BMRI": _summary(
                {"broker_code": "YP", "broker_name": "Mirae", "bval": 2e9, "sval": 0, "nval": 2e9, "nvol": 40, "bfrq": 2, "sfrq": 0},
            ),
        }
    )
    data = _run_activity(["BBRI", "BMRI"], "SS", 7, client)
    assert data["broker"] == "SS"
    assert data["scanned"] == 2
    assert len(data["activities"]) == 1
    a = data["activities"][0]
    assert a["ticker"] == "BBRI"
    assert a["nval"] == 4e9
    assert a["bval"] == 5e9
    assert a["sval"] == 1e9
    assert len(data["errors"]) == 0


def test_broker_activity_handles_missing_and_errors():
    client = _FakeClient(
        {
            "BBRI": _summary({"broker_code": "SS", "broker_name": "Supra", "bval": 1, "sval": 0, "nval": 1, "nvol": 1, "bfrq": 1, "sfrq": 0}),
        }
    )
    data = _run_activity(["BBRI", "TINS"], "SS", 7, client)
    assert len(data["activities"]) == 1
    assert data["errors"] == ["TINS"]


def test_broker_activity_empty_when_broker_inactive():
    client = _FakeClient(
        {
            "BBRI": _summary({"broker_code": "YP", "broker_name": "Mirae", "bval": 1, "sval": 0, "nval": 1, "nvol": 1, "bfrq": 1, "sfrq": 0}),
        }
    )
    data = _run_activity(["BBRI"], "SS", 7, client)
    assert data["activities"] == []
    assert data["errors"] == []


def test_broker_activity_sorts_by_abs_net():
    client = _FakeClient(
        {
            "A": _summary({"broker_code": "SS", "broker_name": "S", "bval": 1e9, "sval": 0, "nval": 1e9, "nvol": 1, "bfrq": 1, "sfrq": 0}),
            "B": _summary({"broker_code": "SS", "broker_name": "S", "bval": 0, "sval": 5e9, "nval": -5e9, "nvol": -1, "bfrq": 0, "sfrq": 1}),
        }
    )
    data = _run_activity(["A", "B"], "SS", 7, client)
    assert [a["ticker"] for a in data["activities"]] == ["B", "A"]