# Portal Runbook

Operational guide for the hosted BRD-intake portal running on Azure Container Apps.

## At a glance

| Field | Value |
| --- | --- |
| Container app | `arch-factory-dev-portal` |
| Resource group | `arch-factory-dev-rg` |
| ACR | `archfactorydevacr.azurecr.io` |
| Public FQDN | `https://arch-factory-dev-portal.politebeach-70e24eed.eastus.azurecontainerapps.io` |
| Dockerfile | [`Dockerfile.portal`](../Dockerfile.portal) |
| Entry point | [`scripts/start_factory_portal.py`](../scripts/start_factory_portal.py) |
| Tests | [`tests/portal/`](../tests/portal) |
| Deploy script | [`scripts/build_and_deploy_portal.ps1`](../scripts/build_and_deploy_portal.ps1) |

## Deploy

**From CI (preferred):** push to `main` touching any of the watched paths in [`.github/workflows/portal-deploy.yml`](../.github/workflows/portal-deploy.yml) — CI runs `pytest tests/portal` first, builds, pushes, updates the revision, then smoke-tests `/health` + `/ready`.

**From a workstation:**

```powershell
pwsh -File scripts/build_and_deploy_portal.ps1
```

## Health probes

| Endpoint | Purpose | Shape |
| --- | --- | --- |
| `/health` | Liveness — always returns 200 if the process is alive | `{"status":"ok","probe":"liveness","uptimeSeconds":N}` |
| `/ready` | Readiness — checks blob storage auth, RUNS snapshot, pipeline pool | `{"status":"ok"\|"degraded","checks":{...}}` |
| `/metrics` | Prometheus-style gauges (when telemetry enabled) | text/plain |

Both probes are exempt from Easy Auth so Container Apps ingress can hit them.

## Configuration (environment)

| Variable | Default | Purpose |
| --- | --- | --- |
| `AAFACTORY_PORT` | `8000` | HTTP listen port |
| `AAFACTORY_API_KEY` | _(unset = no auth)_ | If set, mutation endpoints require `X-Portal-API-Key` match |
| `AAFACTORY_RATE_LIMIT_PER_MINUTE` | `60` | Per-IP request cap on mutation endpoints |
| `AAFACTORY_BLOB_MAX_RETRIES` | `3` | Retry attempts for transient blob failures |
| `AAFACTORY_BLOB_RETRY_BASE_SEC` | `0.5` | Base backoff (0.5s → 1s → 2s) |
| `AAFACTORY_PIPELINE_STUCK_MINUTES` | `30` | Watchdog threshold — runs stuck past this are failed |
| `AAFACTORY_PIPELINE_WATCHDOG_INTERVAL_SECONDS` | `60` | Watchdog sweep interval |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | _(unset)_ | Enables Azure Monitor OpenTelemetry export |
| `AAFACTORY_LOG_JSON` | `1` in container | Structured JSON logs vs plain text |

## Observability

- **Logs:** `az containerapp logs show -n arch-factory-dev-portal -g arch-factory-dev-rg --tail 200`
- **Structured events:** each request logs `{ts, level, logger, msg, method, path, status, durationMs}`.
- **Traces:** when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set, spans are exported via `azure-monitor-opentelemetry`. Correlate via `traceparent` header.
- **Metrics:** see [`OBSERVABILITY_GUIDE.md`](OBSERVABILITY_GUIDE.md).

## Run state

Active runs are persisted to the mounted blob volume after each transition and restored on boot. On restart, queued/running entries come back marked `status=interrupted` so the UI surfaces the break in continuity.

Run terminal states:

| `status` | `returnCode` | Meaning |
| --- | --- | --- |
| `completed` | `0` | Pipeline finished cleanly |
| `failed` | `-1` | Pipeline raised a Python exception |
| `failed` | `-2` | Watchdog terminated a stuck run (check `stderr` for `[watchdog]` marker) |
| `interrupted` | _unset_ | Process restarted while run was active (restored from snapshot) |

## Incident playbooks

### Symptom: `/ready` returns `degraded`

1. Inspect which check failed in the response body.
2. `blobAuth`: managed identity lost role assignment — re-apply `Storage Blob Data Contributor` on the feed/owners/projects containers. Logs will show 401/403s.
3. `runsSnapshot`: snapshot path not writable — check the blob volume mount in the revision spec.
4. `pipelinePool`: pool thread died — revision restart clears it (`az containerapp revision restart`).

### Symptom: Users see "Run timed out and was terminated by the pipeline watchdog"

The watchdog fires when a run sits in `queued`/`running` past `AAFACTORY_PIPELINE_STUCK_MINUTES` (default 30). Causes in order of likelihood:

1. **Worker thread crashed** — grep logs for the run ID before the watchdog marker; look for tracebacks, OOM kills, or segfaults from subprocess tools.
2. **Pool saturated** — if many queued runs age out simultaneously, the pool is undersized. Increase pool size in `_PIPELINE_POOL` or scale out the container app.
3. **Upstream blob timeout** — blob retry exhaustion shows as normal `failed` with `returnCode=-1`; watchdog (`-2`) means no Python-level failure was recorded, implying the worker never returned.

### Symptom: Transient blob 5xx errors in logs

Expected during storage brown-outs. The retry wrapper (`blob_sync._with_retry`) absorbs up to 3 attempts on 408/429/500/502/503/504 + network-level errors. If the rate climbs above a few per minute, check Storage account health in Azure Monitor.

### Symptom: All mutation requests return 401

`AAFACTORY_API_KEY` is set but the caller isn't sending `X-Portal-API-Key`. Public reads (`/`, `/factory-projects.generated.json`) do not require the key — only mutations do. Verify the UI is pulling the key from `localStorage['factoryPortalApiKey']`.

### Symptom: Rate-limited (429) under normal load

Default is 60 req/min per IP on mutation endpoints. Behind a shared egress NAT, many users collapse to one IP. Raise `AAFACTORY_RATE_LIMIT_PER_MINUTE` or lower per-user request volume.

### Symptom: UI shows a run "running" forever

If the wall-clock exceeds 6 minutes in the browser, the client surfaces a timeout without killing the run. Either:

- Let the watchdog reap it server-side (within `AAFACTORY_PIPELINE_STUCK_MINUTES`), or
- Call `GET /api/brd-runs/{id}` directly to inspect the latest state.

## Rollback

Revisions are immutable and tagged by git SHA. To roll back:

```powershell
# List recent revisions
az containerapp revision list -n arch-factory-dev-portal -g arch-factory-dev-rg `
  --query "[].{name:name, image:properties.template.containers[0].image, created:properties.createdTime}" -o table

# Point traffic at a prior revision
az containerapp ingress traffic set -n arch-factory-dev-portal -g arch-factory-dev-rg `
  --revision-weight <previous-revision>=100
```

## Change history

| Phase | Summary | Commit |
| --- | --- | --- |
| 1 | Run-state persist/restore across restarts | earlier |
| 2 | OpenTelemetry tracing + metrics | earlier |
| 3 | Portal test suite (pytest) | earlier |
| 4a | Rate limiting + schema validation + UTC timestamps | `96dd511` |
| 4b | JSON structured logging + deeper `/ready` | `1027bcd` |
| 4c | Easy Auth probe exemption | `d729330` |
| 5 | Blob retry + stuck-run watchdog | `d314b52` |
| 6 | CI pre-deploy test gate + post-deploy smoke | `398e9ca` |
| 7 | BRD polling UX polish | (HEAD~1) |
| 8 | This runbook | (HEAD) |
