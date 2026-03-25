"""Health check and resilience patterns."""
import asyncio
import logging
import time
from typing import Callable, Any, Optional, Awaitable, TypeVar, cast
from functools import wraps
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


T = TypeVar('T')


class HealthCheck(ABC):
    """Base health check interface."""
    
    @abstractmethod
    async def check(self) -> bool:
        """Check if component is healthy."""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Get health check name."""
        pass


class HealthCheckRegistry:
    """Registry for health checks used by services."""
    
    def __init__(self):
        self._checks: dict[str, HealthCheck] = {}
    
    def register(self, check: HealthCheck):
        """Register a health check."""
        self._checks[check.name()] = check
    
    async def check_all(self) -> dict[str, bool]:
        """Run all health checks and return results."""
        results = {}
        for name, check in self._checks.items():
            try:
                results[name] = await check.check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
        return results
    
    async def is_healthy(self) -> bool:
        """Check if all health checks pass."""
        results = await self.check_all()
        return all(results.values())


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker pattern implementation for resilience."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to recover."""
        if self.state == "OPEN" and self.last_failure_time:
            return time.time() - self.last_failure_time >= self.recovery_timeout
        return False
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerException(
                    f"Circuit breaker is OPEN. Recovery timeout: {self.recovery_timeout}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs
    ) -> T:
        """Execute async function with circuit breaker protection."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerException(
                    f"Circuit breaker is OPEN. Recovery timeout: {self.recovery_timeout}s"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            logger.info("Circuit breaker CLOSED after recovery")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60
):
    """Decorator for circuit breaker pattern."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cb = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return cb.call(func, *args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await cb.call_async(func, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        else:
            return cast(Callable[..., T], wrapper)
    
    return decorator


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 10.0,
    backoff_multiplier: float = 2.0,
    *args,
    **kwargs
) -> T:
    """Retry an async function with exponential backoff."""
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                # Add jitter to prevent thundering herd
                jitter = delay * 0.1
                actual_delay = delay + (jitter * (1 - 2 * (time.time() % 1)))
                actual_delay = max(0.001, min(actual_delay, max_delay))
                
                logger.warning(
                    f"Function failed (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {actual_delay:.3f}s: {e}"
                )
                await asyncio.sleep(actual_delay)
                delay = min(delay * backoff_multiplier, max_delay)
            else:
                logger.error(f"Function failed after {max_retries + 1} attempts")
    
    raise last_exception


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, rate: int, per_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            rate: Number of requests allowed
            per_seconds: Time period in seconds
        """
        self.rate = rate
        self.per_seconds = per_seconds
        self.allowance = rate
        self.last_check = time.time()
    
    def allow(self) -> bool:
        """Check if request is allowed."""
        current_time = time.time()
        time_passed = current_time - self.last_check
        
        # Add tokens based on time passed
        self.allowance += time_passed * (self.rate / self.per_seconds)
        
        # Cap allowance at initial rate
        if self.allowance > self.rate:
            self.allowance = self.rate
        
        self.last_check = current_time
        
        if self.allowance < 1:
            return False
        
        self.allowance -= 1
        return True
    
    def reset(self):
        """Reset the rate limiter."""
        self.allowance = self.rate
        self.last_check = time.time()
