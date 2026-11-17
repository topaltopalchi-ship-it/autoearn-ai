"""Rate-limited, cached discovery runtime with adapter health reporting.

This runtime only invokes adapters already registered in AdapterRegistry.
It never performs platform actions or broad crawling.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Callable

from .adapters import AdapterRegistry, DiscoveredLead


class AdapterRateLimitError(RuntimeError):
    """Raised when an adapter exceeds its declared request budget."""


@dataclass(frozen=True)
class AdapterHealth:
    adapter_id: str
    status: str
    last_success_at: str | None
    last_error_at: str | None
    last_error_type: str | None
    consecutive_failures: int
    cached: bool


class DiscoveryRuntime:
    """Apply per-adapter sliding-window limits, TTL caching, and health state."""

    def __init__(
        self,
        registry: AdapterRegistry,
        *,
        cache_ttl_seconds: int = 300,
        clock: Callable[[], float] = monotonic,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        self.registry = registry
        self.cache_ttl_seconds = cache_ttl_seconds
        self._clock = clock
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._calls: dict[str, deque[float]] = {}
        self._cache: dict[str, tuple[float, tuple[DiscoveredLead, ...]]] = {}
        self._health: dict[str, AdapterHealth] = {}

    def _timestamp(self) -> str:
        value = self._utcnow()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def discover(
        self, adapter_id: str, *, force_refresh: bool = False
    ) -> list[DiscoveredLead]:
        manifest = self.registry.get_manifest(adapter_id)
        if manifest is None:
            raise KeyError("adapter is not registered")

        now = self._clock()
        with self._lock:
            cached = self._cache.get(adapter_id)
            if (
                not force_refresh
                and cached is not None
                and now - cached[0] < self.cache_ttl_seconds
            ):
                health = self._health.get(adapter_id)
                if health is not None:
                    self._health[adapter_id] = AdapterHealth(
                        adapter_id=health.adapter_id,
                        status=health.status,
                        last_success_at=health.last_success_at,
                        last_error_at=health.last_error_at,
                        last_error_type=health.last_error_type,
                        consecutive_failures=health.consecutive_failures,
                        cached=True,
                    )
                return list(cached[1])

            calls = self._calls.setdefault(adapter_id, deque())
            while calls and now - calls[0] >= 60:
                calls.popleft()
            if len(calls) >= manifest.requests_per_minute:
                raise AdapterRateLimitError(
                    f"adapter {adapter_id!r} exceeded its per-minute request limit"
                )
            calls.append(now)

        try:
            leads = self.registry.discover(adapter_id)
        except Exception as exc:
            with self._lock:
                previous = self._health.get(adapter_id)
                failures = (previous.consecutive_failures if previous else 0) + 1
                self._health[adapter_id] = AdapterHealth(
                    adapter_id=adapter_id,
                    status="degraded",
                    last_success_at=previous.last_success_at if previous else None,
                    last_error_at=self._timestamp(),
                    last_error_type=type(exc).__name__,
                    consecutive_failures=failures,
                    cached=False,
                )
            raise

        with self._lock:
            self._cache[adapter_id] = (self._clock(), tuple(leads))
            self._health[adapter_id] = AdapterHealth(
                adapter_id=adapter_id,
                status="healthy",
                last_success_at=self._timestamp(),
                last_error_at=None,
                last_error_type=None,
                consecutive_failures=0,
                cached=False,
            )
        return list(leads)

    def get_health(self, adapter_id: str) -> AdapterHealth:
        if self.registry.get_manifest(adapter_id) is None:
            raise KeyError("adapter is not registered")
        with self._lock:
            return self._health.get(
                adapter_id,
                AdapterHealth(
                    adapter_id=adapter_id,
                    status="unknown",
                    last_success_at=None,
                    last_error_at=None,
                    last_error_type=None,
                    consecutive_failures=0,
                    cached=adapter_id in self._cache,
                ),
            )

    def clear_cache(self, adapter_id: str | None = None) -> None:
        with self._lock:
            if adapter_id is None:
                self._cache.clear()
            else:
                self._cache.pop(adapter_id, None)
