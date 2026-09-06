"""Shared lock that serializes ALL yfinance calls.

yfinance's internal data cache is not thread-safe: concurrent `yf.download` /
`Ticker` calls from the asyncio worker pool can return each other's data. Every
yfinance entry point in this app must hold this lock.
"""
from __future__ import annotations

import threading

yf_lock = threading.Lock()