# Self-Healing Quick Reference

## Check Portal Health

```bash
# Liveness (is the portal running?)
curl https://portal/health

# Readiness (can it process BRDs?)
curl https://portal/ready

# Resilience (circuit breaker status)
curl https://portal/api/resilience | jq
```

## Understand Circuit Breaker States

### ✅ CLOSED (Healthy)
```json
{"state": "closed", "failure_count": 0}
```
**Action**: None. Normal operation.

### ⚠️ HALF-OPEN (Recovering)
```json
{"state": "half-open", "failure_count": 1, "success_count": 1}
```
**Action**: Wait. Portal is testing if service recovered. Automatic recovery in progress.

### 🔴 OPEN (Failing)
```json
{"state": "open", "failure_count": 5}
```
**Action**: Investigate!
1. Check logs: `az containerapp logs show -n arch-factory-dev-portal -g arch-factory-dev-rg --tail 100`
2. Likely causes:
   - Blob storage auth failure → Check RBAC
   - Network connectivity → Check NSG/firewall
   - Copilot runner down → Check copilot-runner container
3. Fix the root cause
4. Portal will auto-recover in 60 seconds
5. Or manually restart: `az containerapp revision restart -n arch-factory-dev-portal -g arch-factory-dev-rg`

## Common Failure Patterns

### Pattern: "Circuit OPEN" in Logs
```
ERROR Circuit brd-processor: failure threshold reached (5), opening circuit
```
**Meaning**: BRD processor has failed 5 times in a row.
**Action**: Check `/api/resilience` and investigate root cause.

### Pattern: Multiple Retries
```
WARNING brd-processor: transient error on attempt 2, retrying in 2.34s: TimeoutError
WARNING brd-processor: transient error on attempt 3, retrying in 4.78s: TimeoutError
```
**Meaning**: Transient failures detected, auto-retrying. This is **normal and expected**.
**Action**: Watch the stream. If it resolves on a retry, no action needed. If all retries fail, circuit will open.

### Pattern: Immediate Failure
```
ERROR brd-processor: permanent error on attempt 1, not retrying: ValueError
```
**Meaning**: Bad BRD file (malformed, missing fields). Permanent failure.
**Action**: No retry. User must fix BRD and re-submit.

## Retry Configuration (Advanced)

**More aggressive retries** (for unreliable networks):
```bash
AAFACTORY_BRD_MAX_RETRIES=5
AAFACTORY_BRD_BACKOFF_SEC=0.5
AAFACTORY_BRD_MAX_BACKOFF_SEC=30.0
```

**Less aggressive** (to fail fast):
```bash
AAFACTORY_BRD_MAX_RETRIES=2
AAFACTORY_BRD_BACKOFF_SEC=0.5
AAFACTORY_BRD_MAX_BACKOFF_SEC=10.0
```

**Default** (balanced):
```bash
AAFACTORY_BRD_MAX_RETRIES=3
AAFACTORY_BRD_BACKOFF_SEC=2.0
AAFACTORY_BRD_MAX_BACKOFF_SEC=60.0
```

## Metrics to Monitor

| Metric | Good Value | Bad Value | Action |
|--------|-----------|-----------|--------|
| `circuit_breaker.state` | `"closed"` | `"open"` | Investigate root cause |
| `failures` count | 0–1 | >5 | Check logs for pattern |
| `attempts` > `successes` | Ratio < 1.1 | Ratio > 1.5 | High retry rate, investigate |
| `circuit_breaks` | 0 | >0 | Service had issues |

## Troubleshooting Decision Tree

```
User reports: "BRD submission is slow/failing"
│
├─→ Submit test BRD through portal UI
│   │
│   ├─ Success → Intermittent issue, monitor for pattern
│   │
│   └─ Failure:
│       │
│       ├─→ Check /api/resilience
│       │   │
│       │   ├─ "circuit_breaker.state": "open"
│       │   │   └─→ Root cause: See [Common Failure Patterns] above
│       │   │
│       │   └─ "circuit_breaker.state": "closed"
│       │       └─→ Root cause: Check /ready, logs, or network
│       │
│       └─→ Check /ready probe
│           │
│           ├─ Any "false" checks → Fix that component
│           │
│           └─ All "true" checks → Check logs
│               └─→ `az containerapp logs show -n arch-factory-dev-portal -g arch-factory-dev-rg`
│
└─→ If circuit is OPEN:
    │
    ├─→ Wait 60 seconds (auto-recovery) OR
    │
    └─→ Restart: az containerapp revision restart -n arch-factory-dev-portal -g arch-factory-dev-rg
```

## Alerting Setup

### Azure Monitor KQL Query

```kusto
AppRequests
| where Name == "POST /api/brd-runs"
| where resultCode >= 500
| summarize FailureCount = count() by bin(timestamp, 5m)
| where FailureCount > 3
```

### Alert Rule
- **Trigger**: 5xx response rate > 10% for 5 minutes
- **Action**: Alert ops team to check `/api/resilience`

## Manual Recovery Procedures

### Scenario: Circuit Breaker Stuck Open

**Symptom**: All BRD submissions failing immediately with "Circuit is OPEN"

**Resolution**:
```bash
# Option 1: Wait 60 seconds (automatic)
# Circuit will transition to half-open and test recovery

# Option 2: Immediate restart (recommended if root cause fixed)
az containerapp revision restart \
  --name arch-factory-dev-portal \
  --resource-group arch-factory-dev-rg
```

### Scenario: High Retry Rate

**Symptom**: Logs show many "retrying in Xs" messages

**Resolution**:
1. **Short-term**: Normal and expected if transient issues exist
2. **Verify**: Check if retries eventually succeed or all fail
3. **Long-term**: If persistent, investigate root cause:
   ```bash
   # Check blob storage connectivity
   curl -I https://{storageaccount}.blob.core.windows.net/

   # Check network/firewall logs
   az network watcher packet-capture create ...

   # Check downstream service (copilot-runner, etc.)
   ```

### Scenario: Circuit Breaker Constantly Opening/Closing

**Symptom**: Logs show "opening circuit" and "closing circuit" repeatedly

**Meaning**: Service is on the edge of failure threshold

**Resolution**:
1. **Increase retry threshold** to be more tolerant:
   ```bash
   AAFACTORY_BRD_MAX_RETRIES=5
   ```
2. **Investigate underlying cause** (likely infrastructure issue)
3. **Scale up** if CPU/memory limited
4. **Add retry budget** for slower environments:
   ```bash
   AAFACTORY_BRD_MAX_BACKOFF_SEC=120.0
   ```

## Performance Impact

### Retry Overhead

- **Successful on first attempt**: +0ms (no overhead)
- **Retry on attempt 2**: +2s delay
- **Retry on attempt 3**: +4s delay
- **Average**: ~1s per request (amortized) if 10% of requests retry

### Circuit Breaker Overhead

- **Closed state**: <1ms (no overhead)
- **Open state**: <100μs (immediate rejection, fast-fail)

### Metrics: Negligible

- `/api/resilience` endpoint: <10ms response time
- Metrics tracking: <1% CPU overhead

## Rollback

To disable self-healing (not recommended):

1. **Remove resilience integration from portal**:
   - Revert `scripts/start_factory_portal.py` to pre-resilience version
   - Remove resilience import/executor creation

2. **Or**: Fallback to direct execution (no-op executor):
   ```bash
   # Portal will gracefully fall back if resilience module unavailable
   # (see graceful degradation in start_factory_portal.py)
   ```

---

**For detailed information**, see [RESILIENCE_GUIDE.md](./RESILIENCE_GUIDE.md)
