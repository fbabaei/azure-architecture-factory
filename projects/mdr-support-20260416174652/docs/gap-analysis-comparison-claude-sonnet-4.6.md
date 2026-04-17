# MDR Support — Cross-Model Gap Analysis Comparison

- **Project:** `mdr-support-20260416174652`
- **Analysis date:** 2026-04-17
- **Analyst model:** Claude Sonnet 4.6 (GitHub Copilot)
- **Source files reviewed:**
  - `docs/gap-analysis-claude-opus-4.7.md`
  - `docs/gap-analysis-gpt-5.4.md`
  - `docs/gap-analysis-crest-alpha-v2-preview.md`

---

## Cross-Model Consensus

| Item | Claude Opus 4.7 | GPT-5.4 | Crest Alpha V2 |
|---|---|---|---|
| Total gaps identified | 20 (G1–G20) | 12 | 8 main + medium/low |
| Critical blockers | 4 (G1–G4) | 4 (1–4) | 4 (1–4) |
| High-priority | 8 (G5–G12) | 5 (5–9) | 4 (5–8) |
| Low/polish | 8 (G13–G20) | 3 (10–12) | medium/low improvements |

All three models independently identified the same four critical blockers and broadly the same eight high-priority items. Confidence level in the findings is very high.

---

## The Four Critical Blockers (100% Agreement Across All Three Models)

### 1. No Dockerfile — Blocks deployment entirely

All three models: project targets Container Apps but has no image build artifact.

Impact: cannot containerize and push to ACR without this.  
Effort: ~15 minutes.  
Fix: add a `Dockerfile` (Python 3.11-slim, non-root user, uvicorn entrypoint for `mdr_agent.main:app`) and a `.dockerignore`.

### 2. No RBAC Role Assignments in Bicep — Blocks runtime with 403 errors

All three models: infrastructure disables local auth but does not assign roles to managed identity.

Missing roles: OpenAI User (`5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`), Cognitive Services User (`a97b65f3-24c7-4388-baec-2e87135dc908`), Storage Blob Data Contributor (`ba92f5b4-2d11-453d-a403-e96b0029c9fe`), Cosmos DB Built-in Data Contributor (via `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments`), Key Vault Secrets User (`4633458b-17de-e7ea-6b7d-21b2a73e9e7b`), Monitoring Metrics Publisher.

Impact: every Azure call from the app will fail immediately after deployment.  
Effort: ~30 minutes.  
Fix: add `Microsoft.Authorization/roleAssignments` resources in `infra/main.bicep` scoped to each service, using the managed identity principal ID.

### 3. Observability Provisioned but Not Initialized — No production visibility

All three models: Application Insights and Log Analytics exist, connection string is injected as env var, but `configure_azure_monitor()` is never called.

Impact: no request traces, no dependency spans, no error telemetry in production despite the infrastructure cost.  
Effort: ~10 minutes.  
Fix: initialize `azure-monitor-opentelemetry` in a FastAPI lifespan handler when `APPLICATIONINSIGHTS_CONNECTION_STRING` is present.

### 4. API Security Not Enforced End-to-End — Public exposure of sensitive data

All three models: APIM exists in Bicep but has no API or policy definition; Container App ingress is external; FastAPI has no JWT validation.

Impact: MDR arrangement data (tax compliance records) is publicly reachable on the internet.  
Effort: ~60 minutes (requires an Azure AD app registration).  
Fix: add `Microsoft.ApiManagement/service/apis` and `/policies` with `validate-jwt` against Entra ID; set Container App ingress to internal or restrict to APIM outbound IPs; optionally add app-level bearer-token validation as defense in depth.

---

## High-Priority Gaps (Converged Across Models)

| Gap | Opus | GPT | Crest | Best Suggestion |
|---|---|---|---|---|
| No retry/backoff on Azure calls | G7 | 7 | 5 | Add `tenacity.retry` with exponential backoff for OpenAI, Document Intelligence, Cosmos |
| Upload validation is weak | G6 | 6 | 7 | Enforce max 50 MB, validate content type, reject empty files with 413/415 |
| Clarification parsing is heuristic | G5 | 5 | 6 | Use focused LLM extraction prompt per complex field; keep regex as fallback |
| No audit trail | G12 | 8 | 8 | Add audit Cosmos container or Log Analytics custom table with user identity, action, timestamp, outcome |
| Cosmos turn-id collision risk | G9 | — | — | Append `uuid4().hex[:8]` to turn IDs; add etag-based optimistic concurrency on arrangement writes |
| Jurisdiction heuristic false-positives | G8 | 11 | — | Validate extracted codes against ISO-3166-1 alpha-2 allowlist |
| Key Vault deployed but unused | G11 | 9 | — | Remove (YAGNI for Phase 1) or wire a real secret (e.g. APIM subscription key) |
| Tests lack failure-path coverage | G15 | 10 | — | Add tests for malformed LLM JSON, Azure 429, oversized uploads, Cosmos race conditions |

---

## Recommended Master Implementation Order

Synthesized from all three models' orderings plus criticality.

### Phase 1 — Must-Fix (Critical Blockers)

| Step | Item | Est. time |
|---|---|---|
| 1 | Add Dockerfile + .dockerignore | 15 min |
| 2 | Add RBAC role assignments in Bicep | 30 min |
| 3 | Initialize Azure Monitor / OpenTelemetry in app startup | 10 min |
| 4 | Add APIM API + validate-jwt policy + restrict Container App ingress | 60 min |

### Phase 2 — Stability (High-Priority)

| Step | Item | Est. time |
|---|---|---|
| 5 | Add retry/backoff for OpenAI, Document Intelligence, Cosmos | 45 min |
| 6 | Add upload validation (size, content-type, empty-check) | 20 min |
| 7 | Improve clarification parsing with LLM-backed structured extraction | 120 min |
| 8 | Add audit logging to Cosmos | 90 min |

### Phase 3 — Polish (Optional for Phase 1 Pilot)

| Step | Item | Est. time |
|---|---|---|
| 9 | Fix Cosmos turn-id collisions + add optimistic concurrency | 30 min |
| 10 | Validate jurisdiction codes against ISO-3166 | 15 min |
| 11 | Remove or activate Key Vault | 15 min |
| 12 | Expand test coverage for failure paths | 180 min |
| 13 | Add `/ready` endpoint + OpenAPI tags + response examples | 30 min |

---

## Critical Path to Production Pilot

**Total estimate: 4–5 working days.**

```
Day 1:
  - Dockerfile (15 min)
  - RBAC role assignments (30 min)
  - OpenTelemetry initialization (10 min)

Day 2:
  - APIM API + JWT policy (60 min)
  - Retry/backoff logic (45 min)
  - Upload validation (20 min)

Day 3:
  - Improved clarification parsing (120 min)

Day 4:
  - Audit logging (90 min)
  - Full test suite run + fix breakage (60 min)
```

After this, the project is a defensible Azure pilot. The polish items can follow in Phase 2.

---

## Model-Specific Characterisation

**Claude Opus 4.7** — Most exhaustive: 20 gaps with granular detail, specific role definition GUIDs, and implementation code snippets. Best for architecture deep-dives and Bicep reference.

**GPT-5.4** — Most concise: 12 consolidated gaps, clearly prioritized. Best for quick decision-making and executive communication.

**Crest Alpha V2 (Preview)** — Middle ground: 8 critical + medium/low grouping, evidence-based reasoning with file locations. Best for balanced guidance during implementation.

---

## Bottom Line

The project is a solid Phase 1 proof of concept that matches the BRD's intended workflow. The four critical blockers must be closed before it is a defensible Azure pilot. The stability items (retry, upload validation, audit) should follow as a cohesive block before any user-facing launch.
