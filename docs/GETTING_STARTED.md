# Azure Architecture Factory — Getting Started Guide

For new users with no knowledge of integration and the factory system.

---

## What the System Does

You provide a **business or product requirement document** (BRD/PRD — a plain text description of what you want to build). The system automatically:

1. Generates an **Azure architecture diagram** (.drawio)
2. Scaffolds **Python microservice code**
3. Creates **Bicep infrastructure** (Azure deployment templates)
4. Validates and self-heals infrastructure files
5. Produces a **production-readiness checklist**
6. Optionally **deploys to Azure**
7. Optionally **promotes to the factory portal** (shared team dashboard)

---

## The Two Entry Points

### Entry Point A: GitHub Copilot Chat (`project-orchestrator` agent)

Build and manage projects **locally** on your machine.

#### Step 1: Open GitHub Copilot Chat in VS Code

Ctrl+Alt+I or click the Copilot icon.

#### Step 2: Write Your Requirements

Either inline or save to a file like `my-requirements.md`:

```
I need an e-commerce platform that handles product catalog, shopping cart,
order processing, and payment. Use Azure Container Apps for compute,
Cosmos DB for data, and Azure Service Bus for order messaging.
```

#### Step 3: Invoke the Agent

```
Use the project-orchestrator agent.
Input: my-requirements.md
Project name: my-ecommerce-platform
```

The agent produces a complete folder at `projects/my-ecommerce-platform/`:

| What | Where |
|---|---|
| Architecture diagram | `diagrams/my-ecommerce-platform.drawio` |
| Python service code | `src/<service-name>/main.py` |
| Azure Bicep infrastructure | `infra/main.bicep` + modules |
| Production checklist | `docs/production-checklist.md` |
| Execution logs | `logs/orchestration.log` + per-phase logs |
| Machine-readable state | `project-manifest.json` |

---

### Entry Point B: The Factory Portal (web dashboard)

Submit BRDs through a **local web server** dashboard. View all generated projects in one place — useful for teams.

#### Step 1: Start the Portal Server

```powershell
cd C:\Users\fbabaei\workspace\azure-architecture-factory
python scripts/start_factory_portal.py
```

Output:
```
Factory Portal:  http://127.0.0.1:5501/factory-portal.html
BRD Intake API:  http://127.0.0.1:5501/api/brd-intake
Auth:            None (local dev mode)
```

#### Step 2: Open the Portal in a Browser

Navigate to `http://127.0.0.1:5501/factory-portal.html`

#### Step 3: Submit a BRD

Use the form to paste or upload requirements. The portal:
- Accepts the BRD immediately
- Returns a `run ID`
- Runs the pipeline in the background
- Shows status: `queued → running → completed`

Set **Network Isolation** before submitting:

| Option | Starter infrastructure behavior |
|---|---|
| `Public` | No VNet resources generated |
| `VNet-integrated` | Generates VNet, delegated app subnet, and NSG |
| `Private` | Generates VNet, app subnet, private-endpoint subnet, and NSG |

#### Step 4: View Generated Projects

Once `completed`, the portal displays the project result. It also appears in the `projects/` folder and the `factory-projects.generated.json` feed.

---

## The Bridge: `factory-handoff` Agent

Promotes a **locally-built project** to the **shared factory portal**.

### When to Use It

- You finished building a project locally via `project-orchestrator`
- You want the team to see it on the portal dashboard
- You want a factory-tracked run ID linked to your local project

### Two Ways to Trigger

**Option 1 — Automatically (during orchestration):**

```
Use the project-orchestrator agent.
Input: my-requirements.md
Project name: my-ecommerce-platform
factory: true
```

When `factory: true` is passed, the orchestrator automatically invokes `factory-handoff` after all other phases complete (Phase 6).

**Option 2 — Manually (after the fact):**

If you already have a completed project at `projects/my-ecommerce-platform/`:

```
Use the factory-handoff agent.
Project: projects/my-ecommerce-platform
```

### What It Does

1. Reads `projects/my-ecommerce-platform/docs/requirements.md`
2. POSTs it to `http://127.0.0.1:5501/api/brd-intake`
3. Polls every 10 seconds (up to 3 minutes) for the factory run to finish
4. Retrieves the factory-assigned project slug
5. Writes `factoryHandoff` back into your local `project-manifest.json`:

```json
{
  "factoryHandoff": {
    "status": "complete",
    "runId": "abc-123",
    "factoryProjectSlug": "my-ecommerce-platform",
    "factoryPortalUrl": "http://127.0.0.1:5501/factory-portal.html"
  }
}
```

---

## Using with Remote Azure-Deployed Factory

If the factory portal is **deployed to Azure** (not running locally at `127.0.0.1:5501`), configure `factory-handoff` to point to your remote endpoint.

### Configuration

Set these environment variables before invoking `factory-handoff`:

```powershell
$env:FACTORY_PORTAL_URL = "https://your-factory-deployment.azurewebsites.net"
$env:FACTORY_PORTAL_API_KEY = "your-api-key-or-issued-token"
```

**Alternatively**, pass them as parameters to the agent:

```
Use factory-handoff.
Project: projects/my-app
factoryPortalUrl: https://your-factory-deployment.azurewebsites.net
apiKey: your-api-key-or-issued-token
```

### Authentication Methods

The remote factory supports:

| Method | Setup | When to use |
|---|---|---|
| **No auth (dev)** | Leave `FACTORY_PORTAL_API_KEY` unset | Local development only |
| **Master API key** | Set `FACTORY_PORTAL_API_KEY` to a secret string | Small teams, single admin |
| **Issued HMAC token** | Request a token via admin panel; token is format `<payload>.<signature>` | Production, usage-counted, expiring tokens |
| **Entra ID (Azure AD)** | Set `ENTRA_TENANT_ID` and `ENTRA_CLIENT_ID` on the server; pass Bearer token | Enterprise, federated identity |

### Remote Factory Endpoints

The Azure-deployed factory provides the same REST API as the local version:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/brd-intake` | POST | Submit a BRD (JSON body) |
| `/api/brd-upload` | POST | Submit a BRD (multipart file upload) |
| `/api/brd-runs` | GET | List all pipeline runs |
| `/api/brd-runs/{runId}` | GET | Get status of a specific run |
| `/api/brd-runs/{runId}/project` | GET | Get generated project payload |
| `/factory-portal.html` | GET | View the web dashboard |

### Example: Promote to Remote Factory

```powershell
# Set remote factory credentials
$env:FACTORY_PORTAL_URL = "https://my-factory.azurewebsites.net"
$env:FACTORY_PORTAL_API_KEY = "my-secret-api-key"

# In Copilot Chat:
# Use factory-handoff.
# Project: projects/my-app

# Or during orchestration:
# Use project-orchestrator.
# Input: my-brd.md
# Project name: my-app
# factory: true
# factoryPortalUrl: https://my-factory.azurewebsites.net
# apiKey: my-secret-api-key
```

The `factory-handoff` agent will:
1. Read the local project's BRD from `projects/my-app/docs/requirements.md`
2. POST it to `https://my-factory.azurewebsites.net/api/brd-intake`
3. Poll the remote factory for completion status
4. Retrieve the factory-assigned project slug
5. Update your local `project-manifest.json` with the remote run ID and portal link

---

## Full End-to-End Scenario (Recommended Flow)

```
1. Write your requirements in a .md file
           ↓
2. Start the factory portal server
   python scripts/start_factory_portal.py
           ↓
3. In Copilot Chat:
   "Use the project-orchestrator agent.
    Input: my-requirements.md
    Project name: my-app
    factory: true"
           ↓
4. Orchestrator builds all phases locally into projects/my-app/
           ↓
5. factory-handoff submits it to the portal → you get a factory run ID
           ↓
6. Open http://127.0.0.1:5501/factory-portal.html to see it in the dashboard
```

---

## Prerequisites Summary

| Requirement | How to satisfy |
|---|---|
| VS Code with GitHub Copilot | Already installed |
| Python 3.10+ | `python --version` |
| Activate the venv | `& .venv\Scripts\Activate.ps1` |
| Portal running (for factory handoff) | `python scripts/start_factory_portal.py` |
| Auth (production only) | Set `FACTORY_PORTAL_API_KEY` env var; leave unset for local dev |

---

## Quick Reference: What to Say in Copilot Chat

| Goal | What to type |
|---|---|
| Build a project from requirements | `Use project-orchestrator. Input: my-brd.md. Project name: my-app` |
| Build + deploy to Azure | Add `deploy: true` |
| Build + push to factory portal | Add `factory: true` |
| Use an existing diagram | Add `existing-diagram: diagrams/my-diagram.drawio` |
| Promote an existing project to portal | `Use factory-handoff. Project: projects/my-app` |
| Validate Bicep only | `Use bicep-infrastructure-validator` |
| Generate diagram only | `Use brd-to-architecture-diagram` |

---

## Architecture Diagram Modes

The orchestrator supports two diagram modes:

### Mode A — Generate (default)

No extra arguments needed. The system:
- Parses your requirements
- Uses the MCP Draw.io server to generate an Azure architecture diagram
- Produces `.drawio` file and companion notes

### Mode B — Import Existing Diagram

If you already have a `.drawio` diagram:

```
Use project-orchestrator.
Input: my-requirements.md
Project name: my-app
existing-diagram: diagrams/my-custom-diagram.drawio
```

The system copies your diagram and creates companion notes from it, skipping MCP generation.

---

## Project Folder Structure

After running `project-orchestrator`, inspect the output:

```
projects/
└── my-ecommerce-platform/
    ├── docs/
    │   ├── requirements.md              ← source BRD/PRD
    │   ├── architecture-decisions.md    ← design decisions
    │   └── production-checklist.md      ← readiness report
    ├── diagrams/
    │   ├── my-ecommerce-platform.drawio ← Azure architecture (Draw.io)
    │   └── my-ecommerce-platform.md     ← architecture notes & components
    ├── src/
    │   └── <service-name>/              ← Python microservices
    │       ├── main.py
    │       ├── requirements.txt
    │       └── README.md
    ├── infra/
    │   ├── main.bicep                   ← Azure resource orchestrator
    │   ├── modules/                     ← one module per Azure resource
    │   └── params/
    │       ├── dev.bicepparam
    │       ├── test.bicepparam
    │       └── prod.bicepparam
    ├── tests/
    │   └── test_<service>.py
    ├── logs/
    │   ├── orchestration.log            ← master execution log
    │   ├── phase-1-architecture.log
    │   ├── phase-2-implementation.log
    │   ├── phase-3-infra-validation.log
    │   ├── phase-4-production-review.log
    │   ├── phase-5-deployment.log       ← only if deployment requested
    │   └── phase-6-factory-handoff.log  ← only if factory: true
    ├── project-manifest.json            ← machine state (phases, timestamps, IDs)
    ├── README.md                        ← project overview & quick start
    └── DEPLOY.md                        ← Azure deployment commands
```

---

## Use Cases

### Use Case 1: Individual Developer Building Locally

**Goal:** Quickly prototype a microservice architecture without manual boilerplate.

**Flow:**
1. Write a 1-page requirement sketch
2. Run `project-orchestrator` locally
3. Review generated code, Bicep, and diagram
4. Iterate on details
5. Deploy with `deploy: true` when ready

**Output:** Full, deployable project in `projects/` folder.

---

### Use Case 2: Team Sharing Architectures

**Goal:** Multiple team members build projects and share them through a central portal.

**Flow:**
1. Developer runs `project-orchestrator` locally with `factory: true`
2. Project is auto-submitted to the portal dashboard
3. Team lead reviews the project in the portal
4. Portal provides links to download, preview files, view architecture, and see production readiness

**Output:** Shared project catalog accessible at `http://localhost:5501/factory-portal.html`.

---

### Use Case 3: Architecture as Code (IaC) Generation

**Goal:** Generate production-ready Bicep and Terraform from requirements.

**Flow:**
1. Describe infrastructure needs in a BRD
2. Run `project-orchestrator` → generates Bicep modules + parameters
3. Validate with `bicep-infrastructure-validator` (auto-runs in Phase 3)
4. Deploy with `deploy: true` → Bicep templates deployed to Azure

**Output:** Validated, tested Bicep ready for production.

---

### Use Case 4: Production Readiness Audit

**Goal:** Verify a project is production-ready before deployment.

**Flow:**
1. Build a project locally or via portal
2. Phase 4 automatically runs `production-environment-advisor`
3. Review `docs/production-checklist.md` for any blockers
4. Complete missing items (identity, secrets, networking, monitoring)
5. Deploy when checklist is complete

**Output:** Detailed production readiness report.

---

## Authentication

### Local Development (Default)

No authentication required. Set `FACTORY_PORTAL_API_KEY` env var to empty (or omit it).

Portal runs at `http://127.0.0.1:5501` with no auth.

### Production with API Key

Set the environment variable:

```powershell
$env:FACTORY_PORTAL_API_KEY = "your-secret-key-here"
python scripts/start_factory_portal.py
```

Clients must pass the key in the `X-Factory-Api-Key` header:

```powershell
$headers = @{ "X-Factory-Api-Key" = "your-secret-key-here" }
$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:5501/api/brd-intake" `
    -Method POST `
    -Headers $headers `
    -Body (ConvertTo-Json @{ fileName = "brd.md"; content = $content })
```

### Enterprise with Entra ID (Microsoft Entra ID / Azure AD)

Set environment variables:

```powershell
$env:ENTRA_TENANT_ID = "your-tenant-id"
$env:ENTRA_CLIENT_ID = "your-app-registration-client-id"
python scripts/start_factory_portal.py
```

Clients must pass an OAuth 2.0 Bearer token:

```powershell
$headers = @{ "Authorization" = "Bearer <your-entra-id-token>" }
```

---

## Troubleshooting

### Portal won't start

**Symptom:** `Address already in use`

**Fix:** Change the port:

```powershell
$env:FACTORY_PORTAL_PORT = "5502"
python scripts/start_factory_portal.py
```

---

### Project orchestrator times out

**Symptom:** Agent says "pipeline timeout"

**Fix:**
1. Check logs in `projects/<slug>/logs/`
2. Look for phase-specific logs (e.g., `phase-1-architecture.log`)
3. Review error messages in each log file
4. Re-invoke the agent with verbose output enabled (if available in Copilot Chat settings)

---

### Bicep validation fails

**Symptom:** Phase 3 returns validation errors

**Fix:**
1. Review `projects/<slug>/logs/phase-3-infra-validation.log`
2. Check `projects/<slug>/infra/` for issues:
   - Missing `main.bicep` file
   - Syntax errors in module files
   - Invalid parameter references
3. Manually run `bicep-infrastructure-validator` on the project:

```
Use bicep-infrastructure-validator.
```

---

## Next Steps

1. **Start the portal:**
   ```powershell
   cd C:\Users\fbabaei\workspace\azure-architecture-factory
   python scripts/start_factory_portal.py
   ```

2. **Write a test BRD:**
   Create a file `test-brd.md` with a simple 3-5 sentence requirement description.

3. **Invoke the orchestrator:**
   Open Copilot Chat and say:
   ```
   Use project-orchestrator.
   Input: test-brd.md
   Project name: test-project
   ```

4. **Explore the output:**
   Check `projects/test-project/` for generated artifacts.

5. **Review the production checklist:**
   Read `projects/test-project/docs/production-checklist.md`.

6. **Optional: Push to portal:**
   ```
   Use factory-handoff.
   Project: projects/test-project
   ```

---

## Additional Resources

- [PROJECT_MANIFEST](PROJECT_MANIFEST.md) — Machine-readable project state schema
- [.github/agents/README.md](../.github/agents/README.md) — Agent architecture and coordination
- [infra/README.md](../infra/README.md) — Bicep modules and deployment patterns
- [docs/PRD.md](PRD.md) — Product requirements and capabilities
- [docs/BRD.md](BRD.md) — Business case and adoption goals

