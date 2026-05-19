# Production Readiness Checklist — csa-helper-runtime

**Status: READY for `dev` deploy.** Items below are dev-tier; promotion to `prod` requires the addenda flagged 🟡.

## Runtime
- [x] FastAPI wrapper exposes `/ask`, `/health`, `/health/ready` on port 8080 (FR-1, FR-2).
- [x] Container runs as non-root user (`USER app`, uid 10001).
- [x] Multi-stage Dockerfile vendors upstream `csa-helper` repo at build time (FR-3).
- [x] Liveness + readiness probes wired in `containerapp.bicep`.
- [ ] 🟡 **prod**: pin `CSA_HELPER_REF` to a commit SHA instead of `main` so production builds are reproducible.

## Azure Resources
- [x] Container App, Container Apps Environment, ACR (Basic), Key Vault, Log Analytics, App Insights, UAMI all in template.
- [x] Region: `eastus2`.
- [x] **Existing** AOAI account `fbfoundrywestus` (`rg-fbabaei-2653`) referenced via `existing` + cross-RG role assignment. **No new AOAI account is created.**

## Identity & RBAC
- [x] Single user-assigned Managed Identity reused for all dataplane calls (NFR-5).
- [x] Three role assignments only (least privilege):
  - `Cognitive Services OpenAI User` on AOAI account.
  - `Key Vault Secrets User` on the new vault.
  - `AcrPull` on the new ACR.
- [x] Container App pulls images from ACR using the same UAMI (no admin password).
- [ ] **Pre-deploy**: deployer must hold `Owner` or `User Access Administrator` on `rg-fbabaei-2653` so the cross-RG AOAI role assignment can be created.

## Networking
- [x] Public ingress on 8080 (matches BRD Network Tier = public).
- [x] HTTPS only (`allowInsecure: false`).
- [ ] 🟡 **prod**: front with APIM or Azure Front Door + WAF; add IP allowlist / Easy Auth (BRD §7 defers AuthN/AuthZ to v2).

## Secrets
- [x] No secrets in source, image, or plain env vars (NFR-4).
- [x] AOAI endpoint stored as Key Vault secret `aoai-endpoint`.
- [x] Container App `secrets[]` uses `keyVaultUrl` + `identity` for KV reference.
- [x] App Insights connection string stored as a Container App secret (output of the AI module — never persisted to repo).

## Monitoring
- [x] App Insights wired via `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- [x] One custom event per `/ask` with all 5 FR-6 fields (`prompt_chars`, `specialist_count`, `tool_hops`, `latency_ms`, `model_deployment`).
- [x] Container Apps logs ship to Log Analytics (30-day retention, NFR-3).
- [ ] 🟡 **prod**: add an alert rule on `requests/failed > X` and on AOAI 429s (latency proxy).

## Deployment Prerequisites
- Azure CLI ≥ 2.55, Bicep ≥ 0.32 (`az bicep upgrade` recommended; current 0.43.1 available).
- Logged-in principal with `Contributor` on the deployment RG **and** `User Access Administrator` on `rg-fbabaei-2653`.
- Initial deploy uses `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest` so the platform comes up before the runtime image is built. After Phase 5, rebuild + push the runtime image and update `containerImage` in `dev.bicepparam`, then redeploy.

## Blockers
- **None.** All gates passed.
