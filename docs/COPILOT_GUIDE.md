# Copilot Guide — BRD Copilot & Project Copilot

The Azure Architecture Factory (AAF) portal ships with **two distinct AI copilots**. Each is scoped to a specific job and has different capabilities, safety rails, and UI affordances.

| | 💬 BRD Copilot | 🛠️ Project Copilot |
|---|---|---|
| **Where** | Floating button, **bottom-LEFT** of portal | Per-project side panel (from a project card: *🛠️ Ask Copilot*) |
| **Color** | Green accent (`#1c7a33`) | Indigo / violet accent (`#5b3fd4`) |
| **Icon** | 💬 | 🛠️ |
| **Scope** | Authoring + reviewing BRDs | One specific, already-generated project |
| **Grounded in** | Factory capability catalog (no project files) | The project's full file tree (manifest, docs, infra, code) |
| **Tool-enabled?** | No (pure chat) | **Yes** — 6 read-only tools |
| **Writes anything?** | No. Returns drafts you paste. | No. Deploy commands are returned as text only. |
| **Endpoint** | `POST /api/brd-chat` | `POST /api/projects/<slug>/chat` |
| **History scope** | Per browser session | Per browser session, reset when you switch projects |

---

## Prerequisites (both copilots)

Azure OpenAI must be configured on the portal server. Without these env vars, both copilots return a graceful stub message:

```powershell
$env:AZURE_OPENAI_ENDPOINT    = "https://<your-aoai>.openai.azure.com"
$env:AZURE_OPENAI_DEPLOYMENT  = "<gpt-4o or gpt-4o-mini>"
$env:AZURE_OPENAI_API_KEY     = "<key>"
$env:AZURE_OPENAI_API_VERSION = "2024-10-21"   # optional, defaults to 2024-08-01-preview
python scripts/start_factory_portal.py
```

Use API version **`2024-10-21`** or later for the Project Copilot so tool-calling is fully supported.

---

## 💬 BRD Copilot

**Purpose:** help you author or evaluate a Business Requirements Document (BRD) that the factory can turn into an Azure architecture, service code, and infrastructure-as-code.

### Two modes

#### Mode 1 — Draft a new BRD

Open the panel (💬 bottom-left), describe what you want to build in plain English. The copilot asks clarifying questions only when the request is genuinely ambiguous, then returns:

- `reply` — a concise chat message
- `brd_draft` — full BRD markdown, ready to paste
- `suggested_slug` — kebab-case project slug
- `suggested_options` — language (python | dotnet), IaC (bicep | terraform), network tier (public | vnet-integrated | private)

An **⬆ Apply to form** button appears on any draft and drops the suggested values directly into the factory intake form.

#### Mode 2 — Review an existing BRD

Click **📋 Review an existing BRD** in the welcome message, paste your BRD over the `<paste your BRD here>` placeholder, and send. You get:

1. A **scorecard** — total `X/10` plus per-item `✅ / ⚠️ / ❌` with a one-line justification.
2. A **Missing information** section with targeted questions you (and only you) can answer.
3. An **improved `brd_draft`** that fills safe structural gaps (section headers, normalized factory hints) and flags user-answerable gaps inline with `TODO:` markers.

Iterate: answer the questions in the chat, and the copilot replaces TODOs and re-scores.

### BRD readiness rubric (10 points)

| # | Criterion |
|---|-----------|
| 1 | Clear business goal in one sentence |
| 2 | Named primary users / personas and their job-to-be-done |
| 3 | Concrete key requirements (verbs + nouns, not aspirations) |
| 4 | Measurable success criteria (numbers, SLOs, adoption targets) |
| 5 | Explicit out-of-scope section |
| 6 | Data sources and data sensitivity (PII / PHI / PCI / public) |
| 7 | Integration points with existing systems listed |
| 8 | Non-functional requirements (performance, availability, security, compliance) |
| 9 | Timeline or milestone expectations |
| 10 | Factory hints stated or inferable (language, IaC, network tier) |

### BRD Copilot safety

- No tool calls, no file writes, no Azure API calls.
- Never fabricates domain facts (users, SLAs, data sources). Gaps are marked `TODO:`.
- Responses are constrained to a single JSON object with fixed keys.

---

## 🛠️ Project Copilot

**Purpose:** answer grounded questions about **one specific factory-generated project** — its architecture, monthly cost, operations playbook, observability posture, and how to deploy it — using live reads against the project's files.

### Grounding context

Every chat turn starts with an 18 KB bundle built from the project:

- `project-manifest.json`
- All `docs/*.md`
- `infra/main.bicep`, `infra/**/*.bicep`, `infra/**/*.tf`, `infra/params/*.bicepparam`
- A file-tree listing of `src/` and `tests/`

### Tool-calling (Phase 3)

When the context bundle doesn't contain what the model needs, it calls one of 6 read-only tools. The loop runs up to **5 iterations per turn**. When tools are used, the reply ends with a footer: `🛠️ Used: <tool_names>`.

| Tool | What it does | Example trigger |
|---|---|---|
| `describe_my_capabilities()` | Returns this copilot's own capability manifest | "What can you do?" |
| `read_project_file(path)` | Reads up to 20 KB of any file inside the project | "Show me `src/api/main.py`" |
| `list_project_files(glob)` | Globs the project tree, up to 200 paths | "List all bicep modules" |
| `scan_cost_resources()` | Parses `infra/**` for billable Azure resources + SKU hints + heuristic $/month ranges | "What's the monthly bill?" |
| `scan_observability()` | Deterministic 7-point observability checklist | "Is this production-ready for observability?" |
| `prepare_deploy_commands(rg?, loc?)` | Detects Bicep / Terraform / azd and returns copy-paste CLI | "How do I deploy this to westus3?" |

### Observability checklist (7 items)

| # | Signal |
|---|-------|
| 1 | Application Insights |
| 2 | Log Analytics workspace |
| 3 | Health probe endpoint (`/health`, `/healthz`, health checks) |
| 4 | Structured logging (`ILogger<>`, `structlog`, `applicationinsights`) |
| 5 | Alert rules (metric alerts, scheduled query rules) |
| 6 | OpenTelemetry wiring |
| 7 | Diagnostic settings |

### Cost heuristic resources recognized

Containers (Apps, AKS), App Service, Cosmos DB, Storage, Key Vault, Cognitive Services, App Insights, Log Analytics, Container Registry, Service Bus, Event Hub, SQL, Redis, API Management, Virtual Networks, Private Endpoints, Azure AI Search. List prices are heuristic — the copilot always shows its assumptions and recommends verifying with the Azure Pricing Calculator.

### Project Copilot safety

- **Read-only.** No tool writes to disk, shells out, or calls Azure.
- **Path traversal blocked.** `../` and absolute paths return `{"error": "invalid path"}`.
- **Deploy is advisory.** `prepare_deploy_commands` emits CLI strings only — the portal never executes them.
- **Scoped per project.** Each tool receives the slug-resolved `project_root`. One project's chat cannot read another's files.
- **Iteration cap.** At most 5 tool-call rounds per user turn; if exhausted, the copilot tells you so.
- **Output cap.** Each `read_project_file` caps at 20 KB; each `list_project_files` caps at 200 results.

### What it deliberately does NOT have

- ❌ No write tools — can't edit BRD, infra, or code
- ❌ No execution tools — no `terraform apply`, no `az deployment`, no shell
- ❌ No network tools — no live Azure API, GitHub, or external HTTP
- ❌ No cross-project tools — one chat session = one project

---

## Telling the two apart

Both panels are chat windows in the portal, but they are **visually distinct**:

- **BRD Copilot** lives at **bottom-LEFT**, uses a **green** accent, and says "💬 BRD Copilot".
- **Project Copilot** slides in from **bottom-RIGHT** (per project card), uses an **indigo/violet** accent, shows **🛠️ Project Copilot · Tool-enabled** in the header, and includes quick-ask chips for Estimate cost / Observability audit / Operations playbook / Architecture summary / Security posture.

When the Project Copilot uses tools, every reply ends with a footer line like:

```
🛠️ Used: scan_cost_resources, read_project_file
```

That footer is your proof the answer came from a live file scan, not a guess.

---

## FAQ

**Q: Can the copilots deploy my project?**
No. Both are read-only. Project Copilot can *generate* the exact `az` / `azd` / `terraform` commands via `prepare_deploy_commands`, but you copy-paste and run them in your own terminal.

**Q: Can the BRD Copilot apply its draft to the form automatically?**
It offers an **⬆ Apply to form** button. Clicking it copies `brd_draft`, `suggested_slug`, and `suggested_options` into the intake form — *one user click*, not automatic.

**Q: Why did the Project Copilot's observability audit say 0/7 when I have App Insights?**
The scan looks for specific resource types in `infra/` (`Microsoft.Insights/components`, `azurerm_application_insights`). If App Insights is provisioned by a separate process outside the `infra/` folder, the deterministic scan will not see it. Ask the copilot and it can `read_project_file` to verify.

**Q: Can I add more tools to the Project Copilot?**
Yes — any genuinely read-only operation is safe. Candidates under consideration: `run_what_if` (calls `az deployment group what-if` for a dry-run), `check_quotas` (ARM quota API), `scan_security` (secrets / identity / RBAC audit). All would follow the same path-scoping and no-execution rules. Edits to add new tools live in `scripts/start_factory_portal.py` in the `_PROJECT_CHAT_TOOLS` list and `_execute_project_chat_tool` dispatcher.

**Q: Where is history stored?**
Only in the browser session. Refreshing the page clears both copilots' conversation state. Nothing is persisted server-side.

**Q: What if Azure OpenAI is not configured?**
Both copilots detect unset env vars and return a polite stub explaining what to set. The portal stays up and all other features work.

---

## Where this lives

- BRD Copilot — `scripts/start_factory_portal.py` → `_handle_brd_chat`, `_BRD_CHAT_SYSTEM_PROMPT`
- Project Copilot — `scripts/start_factory_portal.py` → `_handle_project_chat`, `_PROJECT_CHAT_TOOLS`, `_execute_project_chat_tool`, tool implementations `_tool_*`
- UI — `factory-portal.html` (two `<script>` IIFEs at end of file, one per copilot)
- Capability manifest the Project Copilot returns from `describe_my_capabilities` — built inline in `_tool_describe_my_capabilities` and mirrors this document
