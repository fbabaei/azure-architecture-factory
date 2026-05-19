# CSA Helper Agent Runtime

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Date** | May 7, 2026 |
| **Status** | APPROVED |
| **Prepared For** | CSA Engineering, Cloud Platform |
| **Sponsor** | CSA Lead |
| **Primary Region** | East US 2 |
| **Network Tier** | public |

---

## 1. Executive Summary

The **CSA Helper Agent Runtime** is an Azure-hosted HTTP service that exposes the existing `csa-helper/agent-framework/` orchestrator + 9 specialist agents as a stateless REST API, backed by Azure OpenAI. It packages an existing Python codebase (no business logic changes) into a production-grade Azure deployment.

The source agents and runtime code already exist at `https://github.com/fbabaei/csa-helper` (folder: `agent-framework/`). This BRD describes only the **hosting layer**: containerization, Azure resources, identity, secrets, and observability.

---

## 2. Business Problem Statement

### 2.1 Local-only execution today
The CSA helper runs only via `python chat.py` on a single workstation. CSAs cannot share the orchestrator from a phone, browser, or chat surface, and there is no central audit trail of which specialist was invoked for which question.

### 2.2 No managed-identity path to Azure OpenAI
The local runtime authenticates via `DefaultAzureCredential` against `az login`. There is no service-principal-free, key-free path for production.

### 2.3 No observability
No latency, error-rate, token-spend, or specialist-routing telemetry is collected today.

---

## 3. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | Expose `POST /ask` accepting `{ "prompt": "<text>" }` and returning `{ "answer": "<text>", "trace": [{agent,request}, ...] }`. |
| FR-2 | Expose `GET /health` and `GET /health/ready` on port 8080. |
| FR-3 | Reuse `csa-helper/agent-framework/build_team.py` unchanged — wrap with FastAPI. |
| FR-4 | Authenticate to Azure OpenAI using the Container App's user-assigned managed identity (no API keys). |
| FR-5 | Read `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` from environment variables; the deployment URL is sourced from a Key Vault secret reference. |
| FR-6 | Emit one Application Insights custom event per `/ask` call: `prompt_chars`, `specialist_count`, `tool_hops`, `latency_ms`, `model_deployment`. |

---

## 4. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | P95 latency < 8s for a single-hop ask, < 20s for multi-specialist routing. |
| NFR-2 | Auto-scale 0–3 replicas on HTTP concurrency (Container Apps scale rule). |
| NFR-3 | Logs and custom events flow to Application Insights; 30-day retention in Log Analytics. |
| NFR-4 | No secrets in source, image, or env vars — only Key Vault references. |
| NFR-5 | RBAC: managed identity has `Cognitive Services OpenAI User` on the AOAI account and `Key Vault Secrets User` on the vault — nothing else. |

---

## 5. Architecture Components (target Azure resources)

- **Azure Container Registry** (Basic) — hosts the runtime image.
- **Azure Container Apps Environment** + one **Container App** (`csa-helper-runtime`), public ingress on 8080, managed identity attached.
- **User-assigned Managed Identity** — single identity reused by Container App for AOAI + Key Vault.
- **Azure Key Vault** — stores AOAI endpoint URL as a secret (`aoai-endpoint`); RBAC-enabled.
- **Azure OpenAI** — **existing** account `fbfoundrywestus` (RG `rg-fbabaei-2653`, deployment `gpt-4o`). Do NOT create a new AOAI; reference the existing one and assign RBAC only.
- **Log Analytics Workspace** + **Application Insights** (workspace-based) — telemetry sink.

Diagram should show: client → Container App (MI) → Azure OpenAI; Container App → Key Vault (secret read); Container App → App Insights.

---

## 6. Implementation

```yaml
implementation:
  language: python
  iac_tool: bicep
  runtime: container-apps
  agents: []   # this project hosts an existing agent runtime; no new agents are declared here
  source_repo: https://github.com/fbabaei/csa-helper
  source_subpath: agent-framework
  notes: |
    Generate a thin FastAPI wrapper at src/api/main.py that imports build_team
    from the vendored agent-framework folder, exposes POST /ask, GET /health,
    GET /health/ready. Dockerfile multi-stage: copy agent-framework/, install
    requirements.txt + fastapi + uvicorn + opencensus-ext-azure, run uvicorn
    on 0.0.0.0:8080. Do NOT modify build_team.py.
```

---

## 7. Out of Scope

- Authentication/authorization on `/ask` (will be added in v2 via APIM or Easy Auth).
- Streaming responses.
- Provisioning a new Azure OpenAI account or model deployment.
- Changes to the csa-helper agent prompts or runtime logic.

---

## 8. Success Criteria

- `curl https://<fqdn>/health` returns 200.
- `curl -X POST https://<fqdn>/ask -d '{"prompt":"Customer wants a Foundry POC milestone next week"}'` returns a JSON answer with a non-empty `trace` array containing at least `security_sentinel`.
- App Insights shows one custom event per request with the fields in FR-6.
- No secrets visible in `az containerapp show` output; AOAI endpoint resolves via Key Vault reference.
