"""A small thread-safe LRU cache with an expiry (used for answers and query embeddings)."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable


class TtlLruCache[K, V]:
    """Bounded, expiring, thread-safe. A `maxsize` of 0 disables caching."""

    def __init__(
        self,
        maxsize: int,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._maxsize, self._ttl, self._clock = maxsize, ttl_seconds, clock
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at > self._ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        if self._maxsize <= 0:
            return
        with self._lock:
            self._items[key] = (self._clock(), value)
            self._items.move_to_end(key)
            while len(self._items) > self._maxsize:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
