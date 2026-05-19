# MDR Support Gap Analysis Rerun

- Date: 2026-04-17
- Model used: Crest Alpha V2 (Preview)
- Model slug: crest-alpha-v2-preview
- Project: mdr-support-20260416174652
- Reviewer role: Danny - Lead / Architect

## Executive Summary

The MDR support project has a coherent Phase 1 application shape: FastAPI endpoints, a two-agent split between chat orchestration and extraction, local fallbacks, deterministic tests, and Bicep coverage for the main Azure resource families. The focused suite passes, and the app imports cleanly without external Azure services.

There are still critical deployment and governance gaps between the stated architecture and the runnable production path. The most important gaps are APIM not being wired to the app or JWT/rate-limit policies, RBAC assignments not being declared in Bicep, no project-local Dockerfile despite Container Apps deployment guidance, AI Search using an admin key in app environment variables, and audit/case-draft containers being provisioned but not used by the application.

Architectural trade-off: the project currently optimizes for fast local demonstration and testability through local fallbacks. That is the right Phase 1 accelerator, but it leaves production enforcement, identity, and audit guarantees incomplete until the Azure edge and runtime wiring are closed.

## Validation Commands and Results

| Command | Working directory | Result |
|---|---|---|
| `python -m pytest projects/mdr-support-20260416174652/tests/test_generated_project.py -q` | repository root | Passed: `12 passed in 9.39s` |
| `python -c "import sys; sys.path.insert(0, r'projects/mdr-support-20260416174652/src'); from fastapi.testclient import TestClient; from mdr_agent.main import app; response = TestClient(app).get('/health'); print(response.status_code); print(response.json())"` | repository root | Passed: status `200`, body `{'status': 'ok', 'timestamp': '2026-04-17T23:16:12.415121+00:00', 'azure_enabled': False}` |

Note: the latest validation evidence was collected from the repository root, matching the path assumptions in the command table.

## Implemented Capabilities

| Capability | Evidence | Assessment |
|---|---|---|
| MDR Q&A | `src/mdr_agent/main.py`, `src/mdr_agent/services/qa_service.py`, `tests/test_generated_project.py` | Implemented with Azure OpenAI path and deterministic local fallback. AI Search retrieval is optional and best-effort. |
| Document upload to draft | `src/mdr_agent/main.py`, `src/mdr_agent/services/document_ingestion.py`, `src/mdr_agent/services/extraction_agent.py` | Implemented. Local text fallback supports tests; Azure path uploads to Blob and calls Document Intelligence. |
| Text prompt to draft | `src/mdr_agent/main.py`, `tests/test_generated_project.py` | Implemented through `/api/case/from-text`. |
| Human-in-the-loop clarification | `src/mdr_agent/services/clarification_service.py`, `src/mdr_agent/services/chat_session.py` | Implemented for mandatory field completion. Structured field parsing is intentionally simple. |
| Draft finalization guard | `src/mdr_agent/main.py` | Implemented with HTTP 409 while mandatory fields remain missing. |
| Local testability | `src/mdr_agent/config.py`, service fallback builders, `tests/test_generated_project.py` | Strong for Phase 1. Offline tests pass without Azure dependencies. |
| Core Azure resource provisioning | `infra/main.bicep` | Bicep provisions Container Apps, APIM, OpenAI, Document Intelligence, AI Search, Blob, Cosmos, Key Vault, managed identity, App Insights, and Log Analytics. |
| Observability bootstrap | `src/mdr_agent/main.py`, `infra/main.bicep` | Partially implemented. App Insights connection string is provided and FastAPI lifespan configures Azure Monitor OpenTelemetry when present. |

## Current Gaps

### Critical

1. APIM is provisioned but not configured as the real security boundary.
   - Evidence: `docs/detailed-architecture.md` and diagram notes state APIM performs JWT validation and rate limits. `infra/main.bicep` provisions an APIM service only; it does not define API operations, backend routing to the Container App, JWT validation policy, subscription policy, or rate-limit policy.
   - Impact: callers can bypass the intended gateway because the Container App ingress is external. Production behavior does not match the documented API gateway architecture.
   - Trade-off: direct external ingress accelerates demos and smoke tests, but weakens the trust boundary.

2. Managed identity RBAC is documented as required but not declared in infrastructure.
   - Evidence: `DEPLOY.md` lists manual role assignments. `diagrams/mdr-support-20260416174652-detailed-architecture.md` lists RBAC assignments. `infra/main.bicep` creates a user-assigned identity but no role assignment resources.
   - Impact: a fresh deployment can provision resources successfully while runtime calls to OpenAI, Document Intelligence, Blob, Cosmos, Search, and Key Vault fail due to missing permissions.
   - Trade-off: manual role assignment keeps the Bicep simpler, but it makes repeatable deployment and audit evidence weaker.

3. Container deployment path is incomplete.
   - Evidence: `DEPLOY.md` instructs `docker build -t <acr>.azurecr.io/mdr-agent:latest .`, but there is no `Dockerfile` under the project root. `infra/main.bicep` defaults to `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`.
   - Impact: the infrastructure can deploy a placeholder image rather than the MDR agent. A new operator cannot build and deploy the actual service from this project alone.

4. AI Search authentication contradicts the managed identity and Key Vault posture.
   - Evidence: `docs/architecture-overview.md` says service-to-service auth uses managed identity and Key Vault for secrets. `infra/main.bicep` injects `AZURE_AI_SEARCH_API_KEY` from `aiSearch.listAdminKeys().primaryKey` directly into the Container App environment.
   - Impact: an admin key becomes application configuration and may appear in deployment state. It also bypasses least-privilege RBAC expectations.

### High

5. Audit-log and case-drafts containers are provisioned but not used by the application.
   - Evidence: `DEPLOY.md` and diagram notes identify `case-drafts` and `audit-log` containers. `infra/main.bicep` provisions both. `src/mdr_agent/services/repository.py` only uses arrangements and sessions.
   - Impact: compliance audit trail, draft snapshots, and immutable event records are architectural claims rather than implemented behavior.

6. Input validation is too thin for production upload handling.
   - Evidence: `src/mdr_agent/main.py` rejects empty uploads only. There is no file size limit, MIME allowlist, malware scanning hook, extension policy, or content normalization guard.
   - Impact: upload endpoints are exposed to large payloads, unexpected binary content, and avoidable downstream processing risk.

7. Structured clarification parsing is not design-complete.
   - Evidence: `src/mdr_agent/services/chat_session.py` uses direct strings and simple comma/semicolon splitting for hallmarks, parties, and jurisdictions.
   - Impact: user answers such as party role, jurisdiction, and TIN can be flattened or lost. This is acceptable for tests but below the stated schema-safe extraction design.

8. Resilience behavior is minimal around external dependencies.
   - Evidence: OpenAI extraction, Document Intelligence, Blob upload, and Cosmos operations do not have explicit retries, timeout policy, circuit breaker behavior, or typed failure translation in the service layer.
   - Impact: transient Azure failures can surface as generic request failures and make support triage harder.

### Medium

9. Observability is present but not operationally complete.
   - Evidence: Azure Monitor OpenTelemetry is configured when a connection string exists, and Log Analytics/App Insights are provisioned. There are no explicit domain events, correlation IDs, dependency dimensions, alert rules, dashboards, or audit event emission.
   - Impact: baseline request telemetry exists, but MDR-specific operational questions are hard to answer during incidents or audits.

10. Test coverage is mostly happy-path and smoke-level.
   - Evidence: `tests/test_generated_project.py` covers layout, health, upload, chat completion, Q&A, off-topic routing, and case flow. It does not cover Azure client failure behavior, invalid uploads, auth boundaries, APIM policies, RBAC assumptions, audit writes, or structured parsing edge cases.
   - Impact: regressions in production concerns can pass the current focused suite.

11. Network isolation is explicitly deferred but still a residual risk.
   - Evidence: `docs/detailed-architecture.md` marks private endpoints and VNet integration as Phase 2. `infra/main.bicep` enables public network access for Key Vault, Cosmos, AI Search, OpenAI, and Document Intelligence.
   - Impact: acceptable for Phase 1 public-tier delivery, but not ready for stricter enterprise compliance environments without a documented exception.

12. Documentation and traceability overstate some infrastructure implementation.
   - Evidence: `docs/traceability-matrix.md` marks Azure governance, secrets, and identity as implemented via `infra/main.bicep`. Current Bicep creates identity and Key Vault but does not complete role assignments, APIM policies, or Key Vault secret references.
   - Impact: audit readers may assume production controls are complete when several are manual or missing.

## Residual Risks

- No critical functional gap was found in the local Phase 1 happy path; tests pass and the local app health probe succeeds.
- Critical production-readiness gaps remain around gateway enforcement, RBAC automation, container buildability, key handling, and audit persistence.
- The local fallback design can mask Azure integration failures unless pre-deployment validation explicitly forces Azure-backed clients.
- The simplified MDR schema may be enough for a Phase 1 demonstration, but it will need business validation against jurisdiction-specific reporting fields before production use.

## Recommended Next Actions

1. Add a project-local Dockerfile and make `DEPLOY.md` build from the MDR project root or a documented build context.
2. Extend `infra/main.bicep` with role assignments for the managed identity, including OpenAI, Document Intelligence, Blob, Cosmos data-plane role, Key Vault Secrets User, Search data access, and monitoring where needed.
3. Wire APIM in Bicep: API import/operations, backend to Container App, JWT validation, subscription or product policy, and rate limits. Then consider disabling direct public access to the Container App or limiting ingress to APIM.
4. Replace `AZURE_AI_SEARCH_API_KEY` injection with managed identity access where supported, or store a least-privilege query key in Key Vault and reference it securely.
5. Implement audit event writes for upload, extraction, clarification turn, draft edit, and finalization events. Use the existing `audit-log` container or remove the claim from Phase 1 docs.
6. Add production upload controls: size limits, MIME allowlist, extension policy, optional malware scanning handoff, and clear HTTP 4xx responses.
7. Replace comma-split structured clarification handling with a schema-constrained parse step, ideally reusing the extraction agent with a smaller prompt and deterministic validation.
8. Add resilience tests and service-level exception mapping for OpenAI, Document Intelligence, Blob, Cosmos, and AI Search failures.
9. Update `docs/traceability-matrix.md` to distinguish `Implemented`, `Provisioned only`, `Manual post-deploy`, and `Deferred` controls.
10. Keep Phase 2 network isolation explicit: VNet-integrated Container Apps, private endpoints, private DNS, and public network access disabled for data and AI resources.

## Files Reviewed

- `README.md`
- `DEPLOY.md`
- `docs/architecture-overview.md`
- `docs/detailed-architecture.md`
- `docs/traceability-matrix.md`
- `diagrams/mdr-support-20260416174652.md`
- `diagrams/mdr-support-20260416174652-detailed-architecture.md`
- `infra/main.bicep`
- `src/mdr_agent/main.py`
- `src/mdr_agent/models.py`
- `src/mdr_agent/config.py`
- `src/mdr_agent/services/chat_session.py`
- `src/mdr_agent/services/clarification_service.py`
- `src/mdr_agent/services/document_ingestion.py`
- `src/mdr_agent/services/extraction_agent.py`
- `src/mdr_agent/services/guardrails.py`
- `src/mdr_agent/services/qa_service.py`
- `src/mdr_agent/services/repository.py`
- `tests/test_generated_project.py`