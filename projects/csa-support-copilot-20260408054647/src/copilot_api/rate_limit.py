from collections import defaultdict, deque
from threading import Lock
from time import time


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, period_seconds: int = 60) -> None:
        self.limit = limit
        self.period_seconds = period_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time()
        threshold = now - self.period_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < threshold:
                bucket.popleft()

            if len(bucket) >= self.limit:
                return False

            bucket.append(now)
            return True