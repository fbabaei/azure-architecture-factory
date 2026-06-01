# Security & Compliance Gate — csa-helper-runtime

Iterations executed: **1**. Final status: **passed**. `critical = 0`, `major = 0`, `minor = 1`.
Compliance frameworks declared in BRD: **none**. Baseline contract only.

## Findings

| ID | Severity | Layer | Finding | Disposition |
|---|---|---|---|---|
| S-1 | minor | infra | Key Vault `publicNetworkAccess: 'Enabled'` (no private endpoint) | Accepted — BRD §1 explicitly sets `Network Tier: public`. Re-evaluate in v2. |

## Baseline Contract Pass

- ✅ No hardcoded secrets in `src/` (grep clean) or `infra/` (only `aoaiEndpoint` is `@secure()` and stored as a Key Vault secret).
- ✅ No API keys to AOAI — `DefaultAzureCredential` via UAMI (FR-4, NFR-5).
- ✅ AOAI endpoint surfaced via Key Vault secret reference, not plain env (NFR-4).
- ✅ Managed identity is user-assigned, single, scoped to least-privilege roles only (NFR-5 verified):
  - `Cognitive Services OpenAI User` on `fbfoundrywestus`
  - `Key Vault Secrets User` on the new vault
  - `AcrPull` on the new ACR
- ✅ Container runs as non-root (`USER app`, uid 10001) — see Dockerfile.
- ✅ ACR `adminUserEnabled: false`.
- ✅ Container App `allowInsecure: false`, `external: true`, port 8080 only.
- ✅ Liveness + readiness probes on `/health` and `/health/ready`.
- ✅ Dependencies declared with `>=` floors mirroring upstream `csa-helper/agent-framework/requirements.txt`. CVE scan deferred to CI (no `safety` / `pip-audit` runner present in repo today; flagged as a follow-up, not a finding because no `high`/`critical` CVE is currently known for the listed floors).

## Notes for Reviewer
- BRD §7 explicitly defers AuthN/AuthZ on `/ask` to v2. The `/ask` endpoint is therefore intentionally unauthenticated — this is a documented BRD decision, not an oversight.
