# CSA Helper Runtime — Architecture Notes

Companion notes for `csa-helper-runtime.drawio`. Per repo conventions, this file is the source of truth when the `.drawio` cannot be machine-parsed.

## Component Inventory

| ID | Azure Service | Name | Scope | Purpose |
|---|---|---|---|---|
| `acr` | Azure Container Registry (Basic) | `csahelperruntimeacr<token>` | project RG | Stores the runtime image. |
| `cae` | Container Apps Environment | `csa-helper-runtime-cae` | project RG | Hosts the Container App, ships logs to Log Analytics. |
| `capp` | Container App | `csa-helper-runtime` | project RG | FastAPI wrapper around `csa-helper/agent-framework`. Public ingress on 8080. UAMI attached. min=0 / max=3 HTTP concurrency rule. |
| `uami` | User-Assigned Managed Identity | `csa-helper-runtime-id` | project RG | Single identity reused for AOAI + Key Vault + ACR pull. |
| `kv` | Key Vault (RBAC) | `csahelperrun<token>kv` | project RG | Stores `aoai-endpoint` secret. RBAC-enabled. |
| `law` | Log Analytics Workspace | `csa-helper-runtime-law` | project RG | 30-day retention. Backs App Insights and the Container Apps Env. |
| `ai` | Application Insights (workspace-based) | `csa-helper-runtime-ai` | project RG | Custom events + traces from the FastAPI process. |
| `aoai` | **EXISTING** Azure OpenAI account | `fbfoundrywestus` | `rg-fbabaei-2653` (external) | Deployment `gpt-4o`. The factory only assigns RBAC; it never creates this resource. |

## Primary Data Flow (POST /ask)
1. Client → Container App (HTTPS, port 8080).
2. FastAPI handler resolves `AZURE_OPENAI_ENDPOINT` from env (sourced from Key Vault secret reference `aoai-endpoint` at deploy time).
3. `build_team.ask()` calls Azure OpenAI using `DefaultAzureCredential` → UAMI token (scope `https://cognitiveservices.azure.com/.default`).
4. AOAI returns chat completions; the orchestrator routes to specialists; each specialist hop is appended to `trace[]`.
5. Container App emits one App Insights custom event with FR-6 fields (`prompt_chars`, `specialist_count`, `tool_hops`, `latency_ms`, `model_deployment`).
6. Container App returns `{ answer, trace }` to the client.

## Cross-Cutting

- **Identity**: a single user-assigned MI is shared across all Azure plane calls (AOAI, Key Vault, ACR pull). No system-assigned identity.
- **Secrets**: only `aoai-endpoint` lives in Key Vault. Deployment name (`gpt-4o`) and api-version (`2024-10-21`) are plain env vars — they are not secrets.
- **RBAC** (created by this template):
  - UAMI → AOAI account (`fbfoundrywestus` in `rg-fbabaei-2653`): `Cognitive Services OpenAI User` (`5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`).
  - UAMI → Key Vault: `Key Vault Secrets User` (`4633458b-17de-408a-b874-0445c86b69e6`).
  - UAMI → ACR: `AcrPull` (`7f951dda-4ed3-4680-a7ca-43fe172d538d`).
- **Networking**: public-tier per BRD. No VNet integration in v1.
- **Observability**: ACA log streaming → Log Analytics; FastAPI process → App Insights via `opencensus-ext-azure`.

## Out of Scope (matches BRD §7)
- AuthN/AuthZ on `/ask`.
- Streaming responses.
- Provisioning new AOAI or model deployment.
- Changes to the agent prompts or `build_team.py`.

## Assumptions
- The deployer has `Owner` or `User Access Administrator` on `rg-fbabaei-2653` so the role assignment on `fbfoundrywestus` can be created cross-RG.
- The csa-helper GitHub repo (`https://github.com/fbabaei/csa-helper`) is reachable from the Docker build context (no private auth required).
- The model deployment name is `gpt-4o` and api-version is `2024-10-21`; both are overridable via Bicep parameters / env vars.
