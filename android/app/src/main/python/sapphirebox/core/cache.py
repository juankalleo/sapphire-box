"""Tiny in-memory TTL cache, shared by every source module.

Search results and detail pages are re-fetched constantly during browsing;
a short-lived cache avoids hammering sites on every keystroke without
needing a real cache backend.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any


class TTLCache:
    def __init__(self, default_ttl: float = 300.0) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


cache = TTLCache()
