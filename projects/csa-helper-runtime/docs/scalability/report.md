# Scalability Gate — csa-helper-runtime

Iterations executed: **1**. Final status: **passed**. `critical = 0`, `major = 0`, `minor = 1`. Services audited: **1**. Infra modules audited: **3** (cae, capp, kv).

## Load profile (BRD-derived + factory defaults)

> The BRD declares latency targets (NFR-1) but no peak RPS / concurrency. Per Phase 2.8 contract, defaults are derived from the chosen scale rule (`http-concurrency: concurrentRequests=10`) and surfaced here for reviewer sign-off.

| Dimension | Value | Source |
|---|---|---|
| P95 latency, single-hop | < 8s | NFR-1 |
| P95 latency, multi-hop | < 20s | NFR-1 |
| Min replicas | 0 | NFR-2 |
| Max replicas | 3 | NFR-2 |
| Concurrent requests per replica (scale signal) | 10 | factory default |
| Implied peak concurrency at max scale | 30 | derived |
| Cold start budget | included in NFR-1's 8s headroom (replica start + AOAI first call) | factory default |

## Findings

| ID | Severity | Layer | Finding | Disposition |
|---|---|---|---|---|
| Sc-1 | minor | code | Uvicorn workers fixed at `--workers 2`; not parameterized | Accepted for v1 — concurrency is dominated by I/O wait on AOAI; one process w/ 2 workers fits comfortably in 1Gi/0.5 CPU. Tune via Bicep `cpu`/`memory` if observed. |

## Code-Layer Pass
- ✅ The FastAPI process is stateless. No in-process session store.
- ✅ AOAI client is constructed once per worker by `build_team()` (singleton via `_init_team`'s memoization).
- ✅ HTTP handler is synchronous because `openai>=1.40` `chat.completions.create` is blocking; uvicorn schedules each request on the threadpool. Multi-worker (`--workers 2`) absorbs concurrent I/O.
- ✅ No unbounded loops: `build_team.ask` caps hand-offs at 6.
- ✅ Health endpoints are O(1) — `/health` returns immediately; `/health/ready` only checks env presence + memoized team.

## Infra-Layer Pass
- ✅ Container App scale rule `http-concurrency` (concurrentRequests=10) is the correct signal for a per-call HTTP service.
- ✅ `min=0`, `max=3` matches NFR-2 (cold-start tolerated by NFR-1's 8s budget).
- ✅ Single-revision mode (`activeRevisionsMode: 'single'`) — clean rollouts.
- ✅ ACR is regional (eastus2) so image pulls don't cross regions.
- ✅ Key Vault is the only point of fan-in for the secret read; per-request KV calls are eliminated by the secret reference (resolved once at revision activation).
- ✅ Log Analytics retention 30 days — matches NFR-3 and avoids unbounded log growth.

## Cost-impact roll-up
- No changes recommended. Min replicas = 0 means idle cost is dominated by Log Analytics (~$0/day at low ingest) + Key Vault (~$0.03/10k ops).
