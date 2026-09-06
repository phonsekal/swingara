"""Best-effort daily request budget guard for the arjum API (1000 req/day).

Vercel serverless instances are ephemeral, so this is a per-instance counter —
accurate within a warm instance, a helpful guard overall. Set ARJUM_DAILY_BUDGET
to leave headroom below the plan's 1000 requests/day.
"""
from __future__ import annotations

import os
import threading
from datetime import date


class _ArjumBudget:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._date: str | None = None
        self._used = 0
        self.budget = int(os.getenv("ARJUM_DAILY_BUDGET", "900"))

    def _roll(self) -> None:
        today = date.today().isoformat()
        if self._date != today:
            self._date = today
            self._used = 0

    def spend(self) -> bool:
        """Register one request. Returns False when the daily budget is exhausted."""
        with self._lock:
            self._roll()
            if self._used >= self.budget:
                return False
            self._used += 1
            return True

    def usage(self) -> dict:
        with self._lock:
            self._roll()
            return {
                "date": self._date,
                "calls_used": self._used,
                "budget": self.budget,
                "remaining": max(0, self.budget - self._used),
            }

    def reset(self) -> None:
        with self._lock:
            self._used = 0


arjum_budget = _ArjumBudget()