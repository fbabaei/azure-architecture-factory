# CSA Helper Agent Runtime

> Source: `docs/brd-samples/brd-csa-helper-runtime.md` (copied at Phase 0).

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | May 7, 2026 |
| Status | APPROVED |
| Primary Region | East US 2 |
| Network Tier | public |

## Executive Summary
Azure-hosted HTTP service that exposes the existing `csa-helper/agent-framework/` orchestrator + 9 specialist agents as a stateless REST API, backed by Azure OpenAI. Hosting layer only — no business-logic changes.

## Functional Requirements
- FR-1: `POST /ask` accepting `{ "prompt": "<text>" }`, returning `{ "answer": "<text>", "trace": [...] }`.
- FR-2: `GET /health` and `GET /health/ready` on port 8080.
- FR-3: Reuse `csa-helper/agent-framework/build_team.py` unchanged — wrap with FastAPI.
- FR-4: AOAI auth via Container App user-assigned managed identity (no API keys).
- FR-5: Read `AZURE_OPENAI_ENDPOINT` (Key Vault secret reference), `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` from env.
- FR-6: One App Insights custom event per `/ask` call: `prompt_chars`, `specialist_count`, `tool_hops`, `latency_ms`, `model_deployment`.

## Non-Functional Requirements
- NFR-1: P95 < 8s single-hop, < 20s multi-hop.
- NFR-2: Auto-scale 0–3 replicas on HTTP concurrency.
- NFR-3: Logs/events to App Insights; 30-day Log Analytics retention.
- NFR-4: No secrets in source/image/env — only Key Vault references.
- NFR-5: MI has only `Cognitive Services OpenAI User` on AOAI account and `Key Vault Secrets User` on the vault.

## Architecture Components
- ACR (Basic), Container Apps Env + Container App (`csa-helper-runtime`), public ingress 8080, MI attached.
- User-assigned Managed Identity (single).
- Key Vault (RBAC-enabled) holding `aoai-endpoint`.
- **Existing** Azure OpenAI account `fbfoundrywestus` in `rg-fbabaei-2653` with deployment `gpt-4o`. RBAC only.
- Log Analytics + App Insights (workspace-based).

## Implementation
```yaml
implementation:
  language: python
  iac_tool: bicep
  runtime: container-apps
  agents: []
  source_repo: https://github.com/fbabaei/csa-helper
  source_subpath: agent-framework
```

## Out of Scope
- Authn/authz on `/ask` (v2).
- Streaming responses.
- New AOAI account or model deployment.
- csa-helper prompt/runtime changes.

## Success Criteria
- `curl https://<fqdn>/health` returns 200.
- `POST /ask` returns JSON with non-empty `trace` array (at least `security_sentinel` for matching prompts).
- App Insights shows custom events with FR-6 fields.
- No secrets in `az containerapp show`; AOAI endpoint resolves via Key Vault reference.
