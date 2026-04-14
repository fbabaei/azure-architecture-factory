# Workflow Guide — How to Use the Factory Step by Step

The **factory-workflow-guide** agent is your always-available coach inside the Azure Architecture Factory. It reads your project's current state, spots mistakes or missing steps, and tells you exactly what to do next — in plain language, with no guesswork.

---

## Who Should Use This

| Situation | Use this guide |
|---|---|
| You are new to the factory and don't know where to start | ✅ Yes — start here |
| You just finished a phase and want to know what comes next | ✅ Yes |
| Something looks wrong or incomplete | ✅ Yes |
| You got an error message and aren't sure what it means | ✅ Yes |
| You want to verify the project is ready before deploying | ✅ Yes |

---

## Before You Start — Pre-flight Checklist

Before running any factory agent for the first time, confirm all five items below. The workflow guide will check these automatically if you tell it you're new.

| # | Item | How to check |
|---|---|---|
| 1 | **Requirements written down** | You have a BRD, PRD, or at least a paragraph describing what the system should do |
| 2 | **Target Azure region chosen** | Default is `eastus`. Others: `westeurope`, `australiaeast` |
| 3 | **Know if you want to deploy** | "Just generate artifacts" needs nothing. "Deploy to Azure" needs Azure CLI + subscription |
| 4 | **Network isolation selected** | Choose `public`, `vnet-integrated`, or `private` in BRD intake |
| 5 | **Azure CLI installed** (only for deploy) | Run `az --version` in a terminal |
| 6 | **Copilot agent mode active** | Open Copilot Chat → click the model picker → select **Agent** |

Once all six are confirmed, you're ready to run `project-orchestrator`.

### Network Isolation Option (New)

When submitting a BRD through the portal, set **Network Isolation** to one of:

| Option | What gets generated |
|---|---|
| `public` | Internet-facing baseline (no VNet resources in starter Bicep) |
| `vnet-integrated` | VNet + delegated app subnet + NSG starter resources |
| `private` | VNet + app subnet + private endpoint subnet + NSG starter resources |

The selected value is carried into generated project metadata and starter infrastructure.

---

## The Factory Workflow — Phase by Phase

```
Phase 0  Write requirements (BRD / PRD / inline text)
   ↓
Phase 1  Generate architecture diagram   → brd-to-architecture-diagram
   ↓
Phase 2  Scaffold code + infrastructure  → azure-architecture-implementer
   ↓
Phase 3  Validate Bicep                  → bicep-infrastructure-validator
   ↓
Phase 4  Production readiness review     → production-environment-advisor
   ↓
Phase 5  Deploy to Azure (optional)      → azure-project-deployer
   ↓
Phase 6a Observability audit (optional)  → project-observability-advisor
Phase 6b Traceability report (optional)  → project-traceability-advisor
   ↓
Phase 7  Promote to factory portal       → factory-handoff
```

Each phase builds on the previous one. Skipping a phase or running them out of order is the most common source of problems — the workflow guide detects and flags this automatically.

---

## How to Invoke the Guide

### Option A — From the portal (recommended)

1. Find your project card in the portal.
2. Click the **🧭 Guide Me** link in the project card footer.
3. A prompt is copied to your clipboard automatically.
4. Open **GitHub Copilot Chat** in VS Code, switch to **Agent mode**, and paste the prompt.
5. The guide reads your project state and responds within seconds.

### Option B — Type it yourself in Copilot Chat

For an existing project:
```
Use factory-workflow-guide.
Project path: projects/my-project-name
Check my current project state, identify any mistakes or missing steps, and tell me exactly what to do next.
```

For a brand-new start:
```
Use factory-workflow-guide. I'm new and haven't started a project yet.
```

For error triage:
```
Use factory-workflow-guide.
Project path: projects/my-project-name
I got this error: [paste error message here]
```

---

## What the Guide Tells You

Every response is structured in three sections:

### 1 — Where You Are
```
Phase 2 — Implementation Scaffolding
Status: complete / 3 services scaffolded, Bicep not yet validated
Last action: azure-architecture-implementer finished at 14:23
```

### 2 — What I Found
Issues are grouped by severity so you always know what to fix first:

| Icon | Severity | Meaning |
|---|---|---|
| 🔴 | **Critical** | Blocks all further progress — fix immediately |
| 🟠 | **Warning** | Will cause problems later if not addressed |
| 🟡 | **Advisory** | Best-practice gap — not a blocker, but worth doing |

Example output:
```
🔴 Critical — infra/ folder is empty.
   Phase 2 (scaffolding) did not produce any Bicep files.
   Fix: Re-run azure-architecture-implementer for this project.

🟡 Advisory — no tests/ folder found.
   Unit tests were not generated.
   Fix: Add pytest tests for each service before deploying to production.
```

### 3 — What To Do Next
```
✅ Recommended next step:

Run: bicep-infrastructure-validator
With: project-path: projects/my-project-name

After that:
  → Phase 4: production-environment-advisor
  → Phase 5: azure-project-deployer (only when phases 3+4 pass)
```

---

## Common Problems the Guide Detects

| Symptom | What the guide tells you |
|---|---|
| No `project-manifest.json` | Project was not created by the orchestrator — re-run `project-orchestrator` |
| Missing `.drawio` file after Phase 1 | Phase 1 failed silently — re-run `brd-to-architecture-diagram` |
| Empty `infra/` folder | Phase 2 stopped before generating Bicep — re-run `azure-architecture-implementer` |
| Bicep validation log has errors | Phase 3 found failures — re-run `bicep-infrastructure-validator` to auto-fix |
| BRD selected `vnet-integrated` or `private` but `infra/main.bicep` has no VNet/NSG resources | Intake option and generated infrastructure are out of sync — re-run BRD intake or regenerate implementation assets |
| Phase 5 complete but no `docs/production-checklist.md` | Phase 4 was skipped — run `production-environment-advisor` now |
| Services have no `requirements.txt` | Dependencies not declared — deployment will fail without them |
| Architecture diagram lists a service not in `src/` | A designed service was not scaffolded — re-run the implementer |
| Logs are older than 7 days | Project may be stale — re-run validation before deploying |

---

## Running the Guide After Every Phase (Recommended)

The recommended pattern is to run the guide as a health check after each phase completes:

```
Phase 1 done → 🧭 Guide Me → confirms diagram exists, recommends Phase 2
Phase 2 done → 🧭 Guide Me → confirms src/ and infra/, warns about missing tests
Phase 3 done → 🧭 Guide Me → confirms Bicep clean, recommends Phase 4
Phase 4 done → 🧭 Guide Me → confirms checklist passes, green-lights Phase 5
```

This costs nothing (no Azure resources are created) and catches mistakes before they become expensive.

---

## Frequently Asked Questions

**Q: Does the guide make changes to my project?**
No. The guide is read-only. It reads files, logs, and the project manifest, then tells you what to do — but it never modifies your code, Bicep, or configuration.

**Q: Can I run it before I've started anything?**
Yes. Tell it "I'm new and haven't started yet" and it will walk you through the pre-flight checklist and tell you exactly what to run and with what arguments.

**Q: What if the guide says everything is fine but something still seems wrong?**
Describe the specific symptom in the prompt, e.g. "the portal shows no projects" or "my deployment succeeded but I can't reach the API endpoint." The guide has specific triage logic for these scenarios.

**Q: How is this different from just reading the README?**
The README describes the system. The guide looks at *your specific project*, compares its actual state against what should be there, and gives you a personalized diagnosis — not generic instructions.

**Q: Can I run the guide on a project someone else created?**
Yes. Point it at any project folder under `projects/` that has a `project-manifest.json`.

---

## Related Resources

- [⚡ Quick Start](QUICKSTART.md) — fastest path from zero to a running project
- [🧭 Getting Started](GETTING_STARTED.md) — full onboarding walkthrough
- [🔄 App Modernization Guide](APP_MODERNIZATION_GUIDE.md) — for legacy application modernization
- [agents/README.md](../.github/agents/README.md) — full list of all factory agents and what they do
