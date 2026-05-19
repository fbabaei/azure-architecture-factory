"""
Self-healing resilience patterns for AAF pipeline execution.

Provides:
- Exponential backoff retry with jitter
- Circuit breaker to prevent cascading failures
- Transient vs permanent error classification
- Metrics tracking (attempt count, failure patterns)
"""

import enum
import logging
import random
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Any, Optional, TypeVar

logger = logging.getLogger(__name__)
UTC = timezone.utc

T = TypeVar("T")


class ErrorClassification(enum.Enum):
    """Categorize errors for retry decision-making."""
    TRANSIENT = "transient"  # Retryable: timeout, I/O, temporary service issue
    PERMANENT = "permanent"  # Not retryable: bad input, auth failure, not found
    UNKNOWN = "unknown"       # Assume transient unless proven otherwise


def classify_error(exc: Exception, context: str = "") -> ErrorClassification:
    """
    Classify an exception as transient or permanent.

    Args:
        exc: The exception to classify
        context: Optional context string for logging
    
    Returns:
        ErrorClassification enum value
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc).lower()

    # Transient markers: timeouts, temporary failures, service issues
    transient_markers = {
        "timeout", "timed out", "temporarily unavailable", "connection reset",
        "connection refused", "connection aborted", "broken pipe",
        "503", "502", "429",  # Service Unavailable, Bad Gateway, Too Many Requests
        "ioerror", "oserror", "socket.error", "connectionerror",
        "deadlock", "lock timeout", "too many open files",
        "errno", "temporary failure",
    }
    
    # Permanent markers: validation, auth, not found
    permanent_markers = {
        "401", "403", "404", "400",  # Auth, Not Found, Bad Request
        "valueerror", "typeerror", "keyerror",
        "filenotfound", "notfound", "invalid", "unauthorized",
        "malformed", "syntax", "authentication failed",
    }

    # Check exception type first
    if exc_type in {"TimeoutError", "asyncio.TimeoutError", "socket.timeout"}:
        return ErrorClassification.TRANSIENT
    
    if exc_type in {"ValueError", "TypeError", "KeyError", "AttributeError", "NameError"}:
        return ErrorClassification.PERMANENT
    
    # Check message content
    combined = f"{exc_type} {exc_msg}".lower()
    
    for marker in permanent_markers:
        if marker in combined:
            logger.debug(f"Classified {context} as PERMANENT: {exc_type} - {exc_msg[:100]}")
            return ErrorClassification.PERMANENT
    
    for marker in transient_markers:
        if marker in combined:
            logger.debug(f"Classified {context} as TRANSIENT: {exc_type} - {exc_msg[:100]}")
            return ErrorClassification.TRANSIENT
    
    # Default to transient for unknown errors (safe assumption)
    logger.debug(f"Classified {context} as UNKNOWN (assuming TRANSIENT): {exc_type}")
    return ErrorClassification.UNKNOWN


@dataclass
class RetryPolicy:
    """Configuration for exponential backoff retry strategy."""
    max_attempts: int = 3
    initial_backoff_sec: float = 1.0
    max_backoff_sec: float = 32.0
    backoff_multiplier: float = 2.0
    jitter_fraction: float = 0.1  # Add ±10% random jitter to backoff
    
    def get_backoff(self, attempt_num: int) -> float:
        """Calculate backoff for attempt number (0-indexed).
        
        Returns exponential backoff with jitter: 1s, 2s, 4s, 8s... capped at max.
        """
        if attempt_num <= 0:
            return 0.0
        
        backoff = self.initial_backoff_sec * (self.backoff_multiplier ** (attempt_num - 1))
        backoff = min(backoff, self.max_backoff_sec)
        
        # Add jitter: ±jitter_fraction % of the backoff value
        jitter = backoff * self.jitter_fraction * (2 * random.random() - 1)
        return max(0.0, backoff + jitter)


@dataclass
class CircuitBreakerState:
    """Track circuit breaker state and metrics."""
    state: str = "closed"  # "closed", "open", "half-open"
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    
    # Thresholds
    failure_threshold: int = 5  # Open after 5 consecutive failures
    success_threshold_half_open: int = 2  # Close after 2 successes in half-open
    recovery_timeout_sec: int = 60  # Wait before trying half-open


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    States:
    - CLOSED: requests pass through normally
    - OPEN: requests fail immediately (too many failures)
    - HALF_OPEN: testing if service recovered (limited requests allowed)
    """
    
    def __init__(self, 
                 name: str = "default",
                 failure_threshold: int = 5,
                 recovery_timeout_sec: int = 60,
                 success_threshold_half_open: int = 2):
        self.name = name
        self.lock = threading.RLock()
        self.state = CircuitBreakerState(
            failure_threshold=failure_threshold,
            recovery_timeout_sec=recovery_timeout_sec,
            success_threshold_half_open=success_threshold_half_open,
        )
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute func() with circuit breaker protection.
        
        Raises:
            RuntimeError: If circuit is open
        """
        with self.lock:
            if self.state.state == "open":
                now = datetime.now(UTC)
                elapsed = (now - self.state.opened_at).total_seconds()
                if elapsed >= self.state.recovery_timeout_sec:
                    # Try recovery
                    logger.info(f"Circuit {self.name}: transitioning to half-open")
                    self.state.state = "half-open"
                    self.state.success_count = 0
                else:
                    raise RuntimeError(
                        f"Circuit {self.name} is OPEN (will retry in {self.state.recovery_timeout_sec - int(elapsed)}s)"
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise
    
    def _on_success(self):
        """Record successful call."""
        with self.lock:
            self.state.failure_count = 0
            if self.state.state == "half-open":
                self.state.success_count += 1
                if self.state.success_count >= self.state.success_threshold_half_open:
                    logger.info(f"Circuit {self.name}: recovered, closing")
                    self.state.state = "closed"
    
    def _on_failure(self, exc: Exception):
        """Record failed call."""
        with self.lock:
            self.state.failure_count += 1
            self.state.last_failure_time = datetime.now(UTC)
            
            if self.state.state == "half-open":
                # Half-open tried and failed → open again
                logger.warning(f"Circuit {self.name}: recovery attempt failed, reopening")
                self._open()
            elif self.state.failure_count >= self.state.failure_threshold:
                logger.error(
                    f"Circuit {self.name}: failure threshold reached ({self.state.failure_count}), "
                    f"opening circuit"
                )
                self._open()
    
    def _open(self):
        """Transition to open state."""
        self.state.state = "open"
        self.state.opened_at = datetime.now(UTC)
        self.state.success_count = 0
    
    def get_state(self) -> dict:
        """Return current state metrics for observability."""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.state,
                "failure_count": self.state.failure_count,
                "success_count": self.state.success_count,
                "last_failure_time": self.state.last_failure_time.isoformat() if self.state.last_failure_time else None,
            }


class ResilientExecutor:
    """
    Execute a function with automatic retry + circuit breaker protection.
    """
    
    def __init__(self,
                 name: str = "executor",
                 retry_policy: Optional[RetryPolicy] = None,
                 circuit_breaker: Optional[CircuitBreaker] = None,
                 transient_errors_only: bool = True):
        self.name = name
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name)
        self.transient_errors_only = transient_errors_only
        self.metrics = {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "circuit_breaks": 0,
        }
    
    def execute(self, 
                func: Callable[..., T],
                *args,
                **kwargs) -> T:
        """
        Execute func with retry + circuit breaker.
        
        Args:
            func: Callable to execute
            *args, **kwargs: Arguments to pass to func
        
        Returns:
            Return value of func
        
        Raises:
            Exception: Original exception if all retries exhausted or circuit open
        """
        last_exc: Optional[Exception] = None
        
        for attempt in range(self.retry_policy.max_attempts):
            self.metrics["attempts"] += 1
            
            try:
                # Try with circuit breaker
                result = self.circuit_breaker.call(func, *args, **kwargs)
                self.metrics["successes"] += 1
                logger.info(
                    f"{self.name}: success on attempt {attempt + 1}/{self.retry_policy.max_attempts}"
                )
                return result
            
            except RuntimeError as exc:
                # Circuit breaker open
                self.metrics["circuit_breaks"] += 1
                logger.error(f"{self.name}: {exc}")
                raise
            
            except Exception as exc:
                last_exc = exc
                classification = classify_error(exc, context=self.name)
                
                if (self.transient_errors_only and 
                    classification == ErrorClassification.PERMANENT):
                    logger.error(
                        f"{self.name}: permanent error on attempt {attempt + 1}, "
                        f"not retrying: {exc}"
                    )
                    self.metrics["failures"] += 1
                    raise
                
                if attempt < self.retry_policy.max_attempts - 1:
                    backoff = self.retry_policy.get_backoff(attempt + 1)
                    logger.warning(
                        f"{self.name}: {classification.value} error on attempt {attempt + 1}, "
                        f"retrying in {backoff:.2f}s: {exc}"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"{self.name}: exhausted all {self.retry_policy.max_attempts} attempts"
                    )
                    self.metrics["failures"] += 1
                    raise
        
        # Should not reach here
        if last_exc:
            raise last_exc
    
    def get_metrics(self) -> dict:
        """Return metrics for monitoring/observability."""
        return {
            **self.metrics,
            "circuit_breaker": self.circuit_breaker.get_state(),
        }


# Global circuit breakers per component (singleton pattern)
_BREAKERS: dict[str, CircuitBreaker] = {}
_BREAKERS_LOCK = threading.Lock()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    with _BREAKERS_LOCK:
        if name not in _BREAKERS:
            _BREAKERS[name] = CircuitBreaker(name)
        return _BREAKERS[name]


def reset_all_breakers():
    """Reset all circuit breakers (for testing / recovery)."""
    with _BREAKERS_LOCK:
        for breaker in _BREAKERS.values():
            with breaker.lock:
                breaker.state.state = "closed"
                breaker.state.failure_count = 0
                breaker.state.success_count = 0
        logger.info("All circuit breakers reset")
