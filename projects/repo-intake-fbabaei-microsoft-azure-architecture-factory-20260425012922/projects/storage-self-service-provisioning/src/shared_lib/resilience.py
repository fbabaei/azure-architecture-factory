from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def with_retry(operation: Callable[[], T], retries: int = 3, delay_seconds: float = 0.3) -> T:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries:
                break
            time.sleep(delay_seconds)
    if last_error is None:
        raise RuntimeError("retry failed without exception")
    raise last_error
