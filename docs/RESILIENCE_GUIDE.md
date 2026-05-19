# AAF Self-Healing & Resilience Implementation

## Overview

Azure Architecture Factory now includes **workflow-level self-healing** capabilities to prevent cascading failures and automatically recover from transient errors. This complements the existing infrastructure-level health checks (Docker HEALTHCHECK, Kubernetes probes).

## Components

### 1. Error Classification (`resilience.py`)

Automatically categorizes exceptions as **transient** or **permanent**:

| Category | Examples | Behavior |
|----------|----------|----------|
| **TRANSIENT** | Timeouts, connection resets, 503/502, deadlocks | Automatically retried |
| **PERMANENT** | Bad input, auth failures, 404/401, type errors | Failed immediately, no retry |
| **UNKNOWN** | Unmapped exceptions | Assumed transient (safe default) |

### 2. Exponential Backoff with Jitter

Retries use configurable exponential backoff to prevent thundering herd:

**Default behavior:**
```
Attempt 1: Immediate
Attempt 2: 2.0s ± 0.2s (random jitter)
Attempt 3: 4.0s ± 0.4s
Attempt 4: 8.0s ± 0.8s
...capped at 60s
```

**Configuration:**
```bash
AAFACTORY_BRD_MAX_RETRIES=3              # Default: 3 attempts
AAFACTORY_BRD_BACKOFF_SEC=2.0            # Initial backoff (seconds)
AAFACTORY_BRD_MAX_BACKOFF_SEC=60.0       # Cap on backoff
```

### 3. Circuit Breaker

Prevents cascading failures when a dependency is degraded:

**State Machine:**

```
┌─────────┐
│ CLOSED  │  Normal operation, requests pass through
└────┬────┘
     │ (5 consecutive failures)
     ↓
┌──────────┐
│   OPEN   │  Failing fast, rejecting requests
└────┬────┘
     │ (wait 60s)
     ↓
┌────────────┐
│ HALF-OPEN  │  Testing recovery (2 successes → close)
└────┬───────┘
     │ (failure)
     ↓
    OPEN (re-open)
```

**Thresholds:**
- Open after 5 consecutive failures
- Half-open after 60 seconds
- Close after 2 successes in half-open state

### 4. Resilient Executor

Wraps BRD document processing with integrated retry + circuit breaker:

```python
output = _BRD_EXECUTOR.execute(
    process_brd_document,
    factory_root,
    brd_path,
    run_id,
    options,
)
```

**Metrics tracked:**
- Total attempts
- Successes / failures
- Circuit breaker state transitions

## Integration Points

### BRD Pipeline Execution

The `/api/brd-runs` endpoint now automatically retries transient failures:

1. **User submits BRD** → Run queued
2. **Worker thread spawned** → Calls `_BRD_EXECUTOR.execute(process_brd_document, ...)`
3. **Transient error** (timeout, I/O) → Automatic retry with backoff
4. **Permanent error** (bad BRD format) → Fail immediately
5. **Service degraded** (too many failures) → Circuit opens, fast-fail subsequent requests

### Observability

#### New Endpoint: `/api/resilience`

Exposes circuit breaker and executor metrics:

```json
{
  "service": "azure-architecture-factory-portal",
  "probe": "resilience",
  "timeUtc": "2026-04-22T14:32:10Z",
  "brdProcessor": {
    "attempts": 42,
    "successes": 40,
    "failures": 2,
    "circuit_breaks": 0,
    "circuit_breaker": {
      "name": "brd-processor",
      "state": "closed",
      "failure_count": 0,
      "success_count": 0,
      "last_failure_time": null
    }
  }
}
```

**Query from monitoring:**
```bash
curl https://arch-factory-dev-portal.politebeach-70e24eed.eastus.azurecontainerapps.io/api/resilience
```

#### Updated `/health` and `/ready` Probes

Both probes now exempt `/api/resilience` from tenant authorization, allowing monitoring systems to poll metrics even in restricted deployments.

## Operational Runbook

### Monitoring Circuit Breaker Health

**Check current state:**
```bash
curl https://{PORTAL_URL}/api/resilience | jq '.brdProcessor.circuit_breaker'
```

**Healthy state:**
```json
{
  "name": "brd-processor",
  "state": "closed",           # ← GOOD
  "failure_count": 0,
  "success_count": 0
}
```

**Degraded state (Half-Open):**
```json
{
  "state": "half-open",        # ← Recovering
  "failure_count": 1,
  "success_count": 1
}
```

**Failed state (Open):**
```json
{
  "state": "open",             # ← BAD: reject requests for 60s
  "failure_count": 5
}
```

### Interpreting Metrics

| Metric | Interpretation |
|--------|---|
| `attempts > successes` | Some failures occurred, circuit breaker is working |
| `circuit_breaks > 0` | Circuit was open at least once (service had issues) |
| `state == "open"` | **Action required:** Service is failing too much, investigate root cause |
| `state == "half-open"` | Service recovering, wait for state to return to "closed" |

### Manual Recovery

If the circuit breaker is stuck open and you've fixed the root issue, you can reset via the portal restart:

```bash
# Restart the container app
az containerapp revision restart \
  --name arch-factory-dev-portal \
  --resource-group arch-factory-dev-rg
```

This clears all in-memory circuit breaker state, but **does not affect persistent run state** (persisted to blob storage).

## Error Classification Examples

### Will Retry (Transient)

```python
socket.timeout("Connection timed out")                    # Timeout
ConnectionError("Connection refused")                     # Temp network issue
Exception("503 Service Unavailable")                      # Upstream degraded
Exception("429 Too Many Requests")                        # Rate limit (retry with backoff)
OSError("Too many open files")                            # Ephemeral resource limit
```

### Will Fail Immediately (Permanent)

```python
ValueError("BRD format invalid")                          # Bad input
KeyError("missing required field")                        # Invalid structure
json.JSONDecodeError("Expecting value: line 1")           # Malformed data
Exception("401 Unauthorized")                             # Auth failure
Exception("404 Not Found")                                # Resource doesn't exist
```

## Configuration Reference

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AAFACTORY_BRD_MAX_RETRIES` | `3` | Max retry attempts for BRD processing |
| `AAFACTORY_BRD_BACKOFF_SEC` | `2.0` | Initial backoff (seconds) |
| `AAFACTORY_BRD_MAX_BACKOFF_SEC` | `60.0` | Maximum backoff between retries |

Example:
```bash
# Retry up to 5 times with aggressive backoff
AAFACTORY_BRD_MAX_RETRIES=5
AAFACTORY_BRD_BACKOFF_SEC=1.0
AAFACTORY_BRD_MAX_BACKOFF_SEC=120.0
```

## Testing Self-Healing

### Simulate Transient Failure

Edit `local_brd_runner.py` to inject a delay/timeout on first call:

```python
import random
if random.random() < 0.3:  # 30% chance
    raise TimeoutError("Simulated I/O timeout")
```

The resilience layer will automatically retry.

### Verify Circuit Breaker

Submit many BRD requests that fail. After 5 failures:

```bash
curl https://{PORTAL_URL}/api/resilience | jq '.brdProcessor.circuit_breaker.state'
# Output: "open"
```

Further requests fail immediately (no processing attempts) until 60 seconds elapse.

## Future Enhancements

1. **Per-service circuit breakers** — Separate breakers for blob storage, copilot runner, etc.
2. **Adaptive thresholds** — Adjust retry count and backoff based on recent success rates
3. **Fallback strategies** — Partial execution or degraded output if primary path fails
4. **Metrics export** — Prometheus-compatible metrics (requires telemetry setup)
5. **Alerting integration** — Azure Monitor alerts when circuit breaks

## References

- [Resilience Module](../scripts/resilience.py) — Core implementation
- [Portal Integration](../scripts/start_factory_portal.py) — BRD executor wrapping
- [Observability Guide](./OBSERVABILITY_GUIDE.md) — General monitoring setup
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html) — Design rationale
