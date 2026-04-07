"""
Resilience helpers: exponential backoff retry, timeout, circuit breaker.
"""
import functools
import logging
import time
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and calls are blocked."""


class _CircuitBreaker:
    def __init__(self, threshold: int, reset_timeout: float = 60.0):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._open_at: Optional[float] = None

    def is_open(self) -> bool:
        if self._open_at is None:
            return False
        if time.monotonic() - self._open_at > self.reset_timeout:
            self._failures = 0
            self._open_at = None
            return False
        return True

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._open_at = time.monotonic()
            logger.warning("Circuit breaker OPENED after %d failures", self._failures)

    def record_success(self) -> None:
        self._failures = 0
        self._open_at = None


_breakers: dict = {}


def get_circuit_breaker(name: str, threshold: int = 5) -> _CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = _CircuitBreaker(threshold)
    return _breakers[name]


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    circuit_name: Optional[str] = None,
):
    """
    Decorator: retries a function with exponential backoff.
    Optionally integrates with a named circuit breaker.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker = get_circuit_breaker(circuit_name or func.__name__) if circuit_name else None

            for attempt in range(max_retries + 1):
                if breaker and breaker.is_open():
                    raise CircuitBreakerOpen(f"Circuit breaker '{circuit_name}' is open; call blocked.")

                try:
                    result = func(*args, **kwargs)
                    if breaker:
                        breaker.record_success()
                    return result
                except exceptions as exc:
                    if breaker:
                        breaker.record_failure()
                    if attempt == max_retries:
                        logger.error(
                            "Function %s failed after %d attempts: %s",
                            func.__name__, max_retries + 1, exc
                        )
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "Attempt %d/%d for %s failed (%s). Retrying in %.1fs...",
                        attempt + 1, max_retries + 1, func.__name__, exc, delay
                    )
                    time.sleep(delay)
        return wrapper
    return decorator
