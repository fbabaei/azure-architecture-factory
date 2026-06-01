# Copilot CLI Runner — Portal Guide

The **Copilot CLI Runner** lets you execute `copilot -p` from the factory portal
against either a specific project (per-project scope) or the whole repository
(repo scope), without leaving the browser. Runs are driven by the `@github/copilot`
npm CLI on the portal host, stream their log back to the modal, and persist under
`outputs/copilot/<runId>/` so you can revisit them later.

---

## Opening the runner

| From | What you get |
|------|--------------|
| Project card → **▶ Copilot CLI** | Per-project scope — `cwd = projects/<slug>/`, runs saved under that project |
| Global **▶ Run in GitHub Copilot** (modernization) | Repo-root scope — `cwd = azure-architecture-factory/`, runs saved under `outputs/copilot/` |

The modal is **persistent and minimizable**:

- **▁ Minimize** → collapses to a floating pill (bottom-right). Log keeps polling; status dot pulses while running, turns solid green on success, red on failure.
- **▣ / click pill** → restore the full modal with state intact.
- **✕ on modal** → stops the live log refresh (run itself keeps going on the server). Prompts you first if a run is still active.
- **✕ on pill** → dismisses the pill only; run continues in the background and can be reopened from the project card.

---

## Controls

| Control | What it does | Server flag |
|---------|--------------|-------------|
| **Prompt** | What Copilot should do | positional arg to `-p` |
| **Model** | Which model to use for this run | `--model <id>` |
| **Agent** | Custom agent from `.github/agents/*.agent.md` | `--agent <name>` |
| **Allowed / Denied tools** | Comma-separated lists layered on top of the portal defaults | `--allow-tool` / `--deny-tool` |
| **Continue last session** | Resumes the previously selected run's session | `--resume=<uuid>` |
| **Refresh** | Reloads the runs list and log | — |
| **▶ Run** | Starts a new run | — |
| **Log / Diff panes** | Streams `session.log` or `git diff` scoped to the project | — |
| **Cancel** | SIGTERMs the child process (visible only while `running`) | — |

### Built-in safety rails

Every run is launched with these baked-in flags — you can only **add** to them:

- `--allow-tool write --allow-tool shell`
- `--deny-tool "shell(git push*)"`
- `--deny-tool "shell(rm -rf*)"`
- `--deny-tool "shell(npm|pnpm|yarn publish*)"`
- `--deny-tool "shell(gh release*)"`
- `--deny-tool "shell(az logout*)"`

Timeout is **1800s**; prompt length is capped at **8000 chars**; max **2 concurrent** runs per scope.

---

## Sample prompts

Copy, paste, tweak. The best prompts are short, verb-first, and name the exact files/folders Copilot should touch.

### 🏗️ Scaffolding & code generation

```
Scaffold a new FastAPI microservice under src/services/notifications/ with:
- a /health GET endpoint returning {"status":"ok"}
- a /notify POST endpoint that accepts {recipient, message} and logs it
- pytest tests under tests/unit/test_notifications.py
Follow the Python conventions in .github/copilot-instructions.md.
```

```
Add an Azure Container Apps module to infra/modules/containerapp-python.bicep
mirroring containerapp-dotnet.bicep. Wire it into infra/main.bicep behind a
`language` parameter. Update infra/params/dev.bicepparam to include a sample.
```

### 🧪 Tests & validation

```
Read projects/order-management-platform/src/orchestrator.py and write missing
unit tests for every public function. Put them in tests/unit/test_orchestrator.py.
Use the same pytest style already in that folder.
```

```
Run `python -m pytest projects/order-management-platform/tests/unit -v --tb=short`
and fix every failure. Report which tests you changed and why.
```

### 🔍 Code review & refactor

```
Review src/shared/telemetry.py for OWASP Top 10 issues, logging hygiene, and
compliance with the Python Conventions section of .github/copilot-instructions.md.
Output findings as a checklist, then apply the low-risk fixes.
```

```
Refactor projects/<slug>/src/*/main.py so every service uses DefaultAzureCredential
and reads config from environment variables only. Do NOT change public APIs.
```

### 📐 Infrastructure

```
Audit infra/main.bicep and every module under infra/modules/. For each resource:
- confirm @description is set on every parameter
- flag any missing @secure() on sensitive params
- confirm managed identity is used (no connection strings)
Produce a findings table, then fix the low-risk items in place.
```

```
Convert projects/<slug>/infra/ from Bicep to Terraform. Produce providers.tf,
variables.tf, main.tf, outputs.tf, and terraform.tfvars.example. Pin azurerm ~> 4.14.
Match the Bicep resource naming exactly.
```

### 📦 Project lifecycle (with custom agents)

Pick these from the **Agent** dropdown to load specialist instructions:

| Agent | Good prompt |
|-------|-------------|
| `project-orchestrator` | `Generate a new project from docs/BRD.md. Name it "inventory-sync". Region eastus. Do not deploy.` |
| `brd-to-architecture-diagram` | `Read docs/BRD.md and produce an Azure architecture diagram at diagrams/inventory-sync.drawio with companion notes.` |
| `bicep-infrastructure-validator` | `Validate every Bicep file under projects/<slug>/infra/ and auto-fix issues you find.` |
| `security-compliance-auditor` | `Audit projects/<slug>/ for secrets, identity, network boundaries, and CVEs. Emit a severity-classified report.` |
| `source-code-maintainer` | `mode: drift-check — compare projects/<slug>/src/ against diagrams/<slug>.drawio and list drift.` |
| `modernization-to-factory` | `Assess the legacy codebase under legacy-app/ and generate an Azure modernization BRD, then hand off.` |

### 🐞 Diagnostics

```
Read logs/portal.err and the last 200 lines of logs/portal.out. Summarize any
errors, correlate them with recent commits via `git log --oneline -20`, and
propose concrete fixes.
```

```
`curl -s http://127.0.0.1:5501/api/copilot-runtime` is returning 500. Look at
scripts/start_factory_portal.py and scripts/copilot_runner.py to find the cause.
Fix it and show me the diff.
```

---

## Prompt-writing tips

1. **Name the files.** "Update `infra/main.bicep`" beats "update the Bicep file".
2. **Name the convention.** Reference `.github/copilot-instructions.md`, a README, or a sibling file as the style source of truth.
3. **Set the output shape.** "Produce a findings table" or "emit unified diff only" keeps Copilot from drifting into prose.
4. **Stage work.** Long tasks → split into two runs and pass `--resume=<uuid>` (the **Continue last session** checkbox) to keep context.
5. **Use agents for recurring workflows.** The `.github/agents/*.agent.md` files encode validated multi-step recipes — picking an agent is worth hundreds of tokens of prompt engineering.
6. **Avoid destructive phrasing.** The deny list blocks `git push`, `rm -rf`, publishes, and `az logout`, but still — prefer "show me the diff" over "push the change".

---

## Run artifacts

Every run writes to `outputs/copilot/<runId>/` (repo scope) or
`projects/<slug>/outputs/copilot/<runId>/` (per-project):

```
metadata.json   # runId, status, cmd, model, agent, sessionId, requestedBy, timings
prompt.txt      # the exact prompt Copilot received
session.log     # stdout + stderr stream
exit.code       # final process exit code (once finished)
```

These are safe to read, diff, and archive.

---

## Related

- `scripts/copilot_runner.py` — the subprocess driver
- `scripts/start_factory_portal.py` — HTTP endpoints (`/api/copilot-runtime`, `/api/copilot-agents`, `/api/copilot-runs[/…]`)
- `.github/agents/` — custom agents available via the **Agent** dropdown
- `.github/copilot-instructions.md` — the global style/behavior rules every run inherits
