# MDR Support — Handoff

Self-contained Python + Azure project. Everything you need is inside this
folder — no dependency on the parent `azure-architecture-factory` repo at
runtime.

## Requirements

### Local dev / tests (no Azure needed)

| Requirement | Version |
|---|---|
| Python | **3.13+** |
| pip | recent |
| Disk | ~200 MB for venv + deps |
| OS | Windows / macOS / Linux |

The code falls back to in-memory stubs when Azure env vars are unset, so
all 19 tests pass without a subscription.

### Azure deployment (optional)

| Requirement | Purpose |
|---|---|
| Azure subscription with quota for Azure OpenAI (`gpt-5.2` + `text-embedding-3-small`), Document Intelligence, AI Search | runtime services |
| Azure CLI 2.60+ | `az deployment group create` |
| Bicep CLI | bundled with recent `az` |
| Docker | build the container image |
| Owner / Contributor on the target subscription | provision + RBAC |

### Microsoft Agent Framework runtime (optional)

Only if you set `AGENT_FRAMEWORK_ENABLED=1`. Otherwise the deterministic
local runtime is used — behaviour is identical. Two-phase install is
handled by:

- Windows: `.\scripts\install_agent_framework.ps1`
- Linux / macOS: `./scripts/install_agent_framework.sh`

## Quickstart

```powershell
# 1. Create venv + install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Run tests (no Azure needed)
python -m pytest tests -v

# 3. Run the API locally (no Azure needed)
python -m uvicorn mdr_agent.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
# -> http://127.0.0.1:8000/docs
```

For the Azure path, follow [`DEPLOY.md`](DEPLOY.md).

## Read these in order

1. [`README.md`](README.md) — project overview.
2. [`docs/architecture-overview.md`](docs/architecture-overview.md) —
   high-level design + alignment with the Compliance Intelligence Agent
   target.
3. [`docs/detailed-architecture.md`](docs/detailed-architecture.md) —
   components and flows.
4. [`docs/production-readiness.md`](docs/production-readiness.md) —
   **must read before prod.** Enumerates the 11 gaps from the current
   deploy-able state.
5. [`DEPLOY.md`](DEPLOY.md) — step-by-step Azure deployment runbook.
6. [`diagrams/mdr-support-20260416174652-detailed-architecture.drawio`](diagrams/mdr-support-20260416174652-detailed-architecture.drawio) —
   open in draw.io or VS Code (extension `hediet.vscode-drawio`).

## Known caveats

- **Placeholder container image.** `infra/main.bicep` defaults
  `containerImage` to the ACR-hosted `mdr-agent:latest`. You must
  build and push your own image before the app actually runs. See the
  "Build and push the MDR agent image" section in
  [`DEPLOY.md`](DEPLOY.md).
- **Tests use in-memory stubs.** A green test suite does **not** prove
  the Azure-connected paths work.
- **Phase 1 production gaps are not fixed.** Private networking, APIM
  SKU, JWT enforcement, Cosmos backup + zone redundancy, Key Vault
  purge protection, metric alerts — all still to-do before real
  production traffic. See
  [`docs/production-readiness.md`](docs/production-readiness.md).
- **Post-deploy bootstrap required.** After the first
  `az deployment group create`, run
  `.\scripts\run_search_index.ps1 -ResourceGroupName <rg>` to create
  the AI Search index and seed the knowledge base corpus.

## Getting help

- Open [`README.md`](README.md) first — it contains the troubleshooting
  notes and test commands.
- For Azure-side issues, the deployment outputs (`containerRegistryLoginServer`,
  `openAiEndpoint`, `cosmosEndpoint`, `apimGatewayUrl`,
  `appInsightsConnectionString`) are your starting point.
