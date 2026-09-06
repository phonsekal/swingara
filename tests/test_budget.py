"""Tests for the arjum request budget guard."""
from __future__ import annotations

import asyncio

import pytest

from app.arjum import ArjumClient, ArjumError
from app.budget import arjum_budget


def test_budget_blocks_after_exhaustion():
    arjum_budget.reset()
    arjum_budget.budget = 2
    try:
        assert arjum_budget.spend() is True
        assert arjum_budget.spend() is True
        assert arjum_budget.spend() is False
        usage = arjum_budget.usage()
        assert usage["calls_used"] == 2
        assert usage["remaining"] == 0
    finally:
        arjum_budget.budget = 900
        arjum_budget.reset()


def test_client_raises_when_budget_exhausted():
    arjum_budget.reset()
    arjum_budget.budget = 0
    try:
        client = ArjumClient("dummy-key")
        with pytest.raises(ArjumError, match="Budget harian"):
            asyncio.run(client.history("BBRI"))
    finally:
        arjum_budget.budget = 900
        arjum_budget.reset()