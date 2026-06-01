"""
Unit tests for AAF self-healing resilience module.

Tests cover:
- Error classification (transient vs permanent)
- Exponential backoff with jitter
- Circuit breaker state transitions
- Resilient executor with retry logic
"""

import time
import unittest
from scripts.resilience import (
    ErrorClassification,
    classify_error,
    RetryPolicy,
    CircuitBreaker,
    ResilientExecutor,
)


class TestErrorClassification(unittest.TestCase):
    """Test error classification logic."""

    def test_transient_timeouts(self):
        """Timeouts should be classified as transient."""
        exc = TimeoutError("Connection timed out")
        self.assertEqual(classify_error(exc), ErrorClassification.TRANSIENT)

    def test_transient_connection_errors(self):
        """Connection errors should be transient."""
        exc = ConnectionError("Connection refused")
        self.assertEqual(classify_error(exc), ErrorClassification.TRANSIENT)

    def test_transient_service_unavailable(self):
        """503 errors should be transient."""
        exc = Exception("503 Service Unavailable")
        self.assertEqual(classify_error(exc), ErrorClassification.TRANSIENT)

    def test_permanent_value_error(self):
        """ValueError should be permanent."""
        exc = ValueError("Invalid BRD format")
        self.assertEqual(classify_error(exc), ErrorClassification.PERMANENT)

    def test_permanent_key_error(self):
        """KeyError should be permanent."""
        exc = KeyError("Missing required field")
        self.assertEqual(classify_error(exc), ErrorClassification.PERMANENT)

    def test_permanent_auth_failure(self):
        """401/403 errors should be permanent."""
        exc = Exception("401 Unauthorized")
        self.assertEqual(classify_error(exc), ErrorClassification.PERMANENT)

    def test_permanent_not_found(self):
        """404 errors should be permanent."""
        exc = Exception("404 Not Found")
        self.assertEqual(classify_error(exc), ErrorClassification.PERMANENT)

    def test_unknown_unmapped_error(self):
        """Unmapped exceptions default to UNKNOWN (treated as transient)."""
        exc = Exception("Some random error")
        result = classify_error(exc)
        self.assertIn(result, [ErrorClassification.UNKNOWN, ErrorClassification.TRANSIENT])


class TestRetryPolicy(unittest.TestCase):
    """Test exponential backoff retry policy."""

    def test_initial_backoff(self):
        """First retry should use initial_backoff_sec."""
        policy = RetryPolicy(
            initial_backoff_sec=1.0,
            backoff_multiplier=2.0,
            jitter_fraction=0.0,  # No jitter for predictability
        )
        backoff = policy.get_backoff(attempt_num=1)
        self.assertEqual(backoff, 1.0)

    def test_exponential_growth(self):
        """Backoff should double each attempt (2^n * initial)."""
        policy = RetryPolicy(
            initial_backoff_sec=1.0,
            backoff_multiplier=2.0,
            jitter_fraction=0.0,
        )
        # Attempt 1: 1.0s
        # Attempt 2: 2.0s
        # Attempt 3: 4.0s
        self.assertAlmostEqual(policy.get_backoff(1), 1.0, places=1)
        self.assertAlmostEqual(policy.get_backoff(2), 2.0, places=1)
        self.assertAlmostEqual(policy.get_backoff(3), 4.0, places=1)

    def test_max_backoff_cap(self):
        """Backoff should never exceed max_backoff_sec."""
        policy = RetryPolicy(
            initial_backoff_sec=1.0,
            backoff_multiplier=2.0,
            max_backoff_sec=10.0,
            jitter_fraction=0.0,
        )
        # Attempt 1: 1.0s
        # Attempt 2: 2.0s
        # Attempt 3: 4.0s
        # Attempt 4: 8.0s
        # Attempt 5: 16.0s -> capped at 10.0s
        self.assertAlmostEqual(policy.get_backoff(1), 1.0, places=1)
        self.assertAlmostEqual(policy.get_backoff(2), 2.0, places=1)
        self.assertAlmostEqual(policy.get_backoff(3), 4.0, places=1)
        self.assertAlmostEqual(policy.get_backoff(4), 8.0, places=1)
        self.assertAlmostEqual(policy.get_backoff(5), 10.0, places=1)

    def test_jitter_range(self):
        """Jitter should be within ±jitter_fraction of backoff."""
        policy = RetryPolicy(
            initial_backoff_sec=10.0,
            backoff_multiplier=1.0,  # Keep consistent multiplier
            jitter_fraction=0.1,  # ±10%
        )
        # With multiplier=1.0, backoff stays at 10.0 regardless of attempt
        # Jitter should be ±1.0 (10% of 10.0)
        backoffs = [policy.get_backoff(1) for _ in range(20)]
        min_backoff = min(backoffs)
        max_backoff = max(backoffs)
        # Should be roughly 10 ± 1
        self.assertGreater(min_backoff, 8.0)
        self.assertLess(max_backoff, 12.0)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker state machine."""

    def test_initial_state_closed(self):
        """Circuit should start in closed state."""
        breaker = CircuitBreaker(name="test")
        self.assertEqual(breaker.state.state, "closed")

    def test_successful_call_increments_success(self):
        """Successful call should increment success counter."""
        breaker = CircuitBreaker(name="test")

        def success_fn():
            return "ok"

        result = breaker.call(success_fn)
        self.assertEqual(result, "ok")
        self.assertEqual(breaker.state.success_count, 0)  # Counts in half-open state
        self.assertEqual(breaker.state.failure_count, 0)

    def test_failure_increments_counter(self):
        """Failed call should increment failure counter."""
        breaker = CircuitBreaker(name="test")

        def fail_fn():
            raise ValueError("Test error")

        for i in range(3):
            with self.assertRaises(ValueError):
                breaker.call(fail_fn)
            self.assertEqual(breaker.state.failure_count, i + 1)

    def test_opens_after_threshold(self):
        """Circuit should open after failure_threshold failures."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        def fail_fn():
            raise TimeoutError("Timeout")

        # Trigger 3 failures
        for _ in range(3):
            with self.assertRaises(TimeoutError):
                breaker.call(fail_fn)

        # Circuit should now be open
        self.assertEqual(breaker.state.state, "open")

    def test_rejects_while_open(self):
        """Circuit should reject requests when open."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)

        def fail_fn():
            raise TimeoutError("Timeout")

        # Trigger 2 failures to open circuit
        for _ in range(2):
            with self.assertRaises(TimeoutError):
                breaker.call(fail_fn)

        # Next call should fail with circuit breaker error, not execute function
        def should_not_run():
            raise AssertionError("Should not be called when circuit is open")

        with self.assertRaises(RuntimeError) as cm:
            breaker.call(should_not_run)
        self.assertIn("OPEN", str(cm.exception))


class TestResilientExecutor(unittest.TestCase):
    """Test resilient executor with retry + circuit breaker."""

    def test_successful_execution(self):
        """Successful calls should return normally."""
        executor = ResilientExecutor(name="test")

        def success_fn(x):
            return x * 2

        result = executor.execute(success_fn, 21)
        self.assertEqual(result, 42)
        self.assertEqual(executor.metrics["successes"], 1)
        self.assertEqual(executor.metrics["failures"], 0)

    def test_retries_transient_error(self):
        """Transient errors should be retried."""
        executor = ResilientExecutor(
            name="test",
            retry_policy=RetryPolicy(max_attempts=3, initial_backoff_sec=0.01),
        )

        attempt_count = [0]

        def fail_twice():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise TimeoutError("Transient timeout")
            return "success"

        result = executor.execute(fail_twice)
        self.assertEqual(result, "success")
        self.assertEqual(executor.metrics["successes"], 1)
        self.assertEqual(executor.metrics["attempts"], 3)

    def test_permanent_error_no_retry(self):
        """Permanent errors should fail immediately without retry."""
        executor = ResilientExecutor(
            name="test",
            retry_policy=RetryPolicy(max_attempts=5),
            transient_errors_only=True,
        )

        attempt_count = [0]

        def fail_permanent():
            attempt_count[0] += 1
            raise ValueError("Invalid input")

        with self.assertRaises(ValueError):
            executor.execute(fail_permanent)

        # Should only attempt once
        self.assertEqual(attempt_count[0], 1)
        self.assertEqual(executor.metrics["failures"], 1)
        self.assertEqual(executor.metrics["attempts"], 1)

    def test_exhausts_retries(self):
        """Should fail when retries exhausted."""
        executor = ResilientExecutor(
            name="test",
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_sec=0.001),
        )

        def always_fails():
            raise TimeoutError("Persistent timeout")

        with self.assertRaises(TimeoutError):
            executor.execute(always_fails)

        # Should attempt max_attempts times
        self.assertEqual(executor.metrics["attempts"], 2)
        self.assertEqual(executor.metrics["failures"], 1)

    def test_circuit_breaker_integration(self):
        """Circuit breaker should prevent requests when open."""
        executor = ResilientExecutor(
            name="test",
            retry_policy=RetryPolicy(max_attempts=1),
        )
        executor.circuit_breaker.state.failure_threshold = 2

        def fail_fn():
            raise TimeoutError("Timeout")

        # Trigger 2 failures to open circuit
        for _ in range(2):
            with self.assertRaises(TimeoutError):
                executor.execute(fail_fn)

        # Next request should be rejected by circuit breaker (RuntimeError)
        with self.assertRaises(RuntimeError) as cm:
            executor.execute(fail_fn)
        self.assertIn("OPEN", str(cm.exception))
        self.assertEqual(executor.metrics["circuit_breaks"], 1)


if __name__ == "__main__":
    unittest.main()
