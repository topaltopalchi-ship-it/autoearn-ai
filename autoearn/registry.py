"""In-memory registry for candidate opportunity sources."""
from __future__ import annotations
from threading import RLock
from .discovery import SourceCandidate
from .opportunities import normalize_url

class SourceRegistry:
    """Thread-safe registry; new sources are auto-approved for manual access."""
    def __init__(self):
        self._items = {}
        self._lock = RLock()

    def add(self, candidate):
        if not isinstance(candidate, SourceCandidate):
            raise TypeError("candidate must be a SourceCandidate")
        key = candidate.duplicate_key
        with self._lock:
            existing = self._items.get(key)
            if existing is not None:
                return existing, False
            self._items[key] = candidate
            return candidate, True

    def get(self, url):
        with self._lock:
            return self._items.get(normalize_url(url))

    def list(self, status=None):
        if status is not None and status != "eligible":
            raise ValueError("the only opportunity status is eligible; archived records are managed separately")
        with self._lock:
            items = list(self._items.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=lambda item: (item.name.casefold(), item.canonical_url))

    def __len__(self):
        with self._lock:
            return len(self._items)
