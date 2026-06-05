# Architecture, Design & Operations Review — Casewright vs. Case Assistant Agent

> **Status:** Current as of 2026-06-05. This review reflects the evolved architecture after both
> projects converged on Service Bus, a scheduler Function, and Foundry IQ retrieval. It replaces an
> earlier comparison that predated those changes (e.g. one that claimed "case-assistant-agent has no
> messaging"), which is no longer accurate.

Both projects deliver the **same product**: grounded, agentic case Q&A with citations,
incremental SharePoint ingestion into Azure AI Search, Foundry IQ retrieval, Cosmos-backed chat
history, and React + Teams frontends. The differences are now almost entirely in **how the system
is structured, hosted, secured, and operated** — not in what it does.

This review is evidence-based, drawn from the current source of both repositories:

- `case-assistant-agent` — `c:\dev\workspace\case-assistant-agent`
- `casewright` — `c:\dev\workspace\azure-architecture-factory\projects\casewright`

---

## 1. What they now have in common

These were once differentiators and no longer are:

- **Event-driven sync.** Both have a Service Bus queue and a queue **worker** that runs SharePoint
  sync jobs and conditionally triggers indexers.
  - case-assistant-agent: `infra/modules/servicebus.bicep`,
    `backend/app/services/sharepoint_sync_queue_worker.py`.
  - casewright: `infra/modules/servicebus.bicep`, `src/casewright/worker/sb_worker.py`.
- **Scheduled trigger.** Both ship a `sharepoint_sync_scheduler` Azure Function.
- **Foundry IQ retrieval.** Both retrieve at query time through a Foundry IQ knowledge base over
  Azure AI Search, with a hosted Foundry agent (`scripts/deploy_agent.py` in each).
- **Incremental sync.** Both use a per-file high-water-mark and only trigger the indexer on net
  change.
- **Cosmos chat history** with a **hierarchical partition key** (tenant → user → conversation).
- **Identity-first intent.** Both aim for managed identity + data-plane RBAC and disabling local
  auth on the data/AI services.

Because the capability set and the core data/AI platform are equivalent, the rest of this review
focuses on the parts that genuinely differ.

---

## 2. Side-by-side summary

| Dimension | case-assistant-agent | casewright |
| --- | --- | --- |
| **Code layout** | `backend/app/` package (`app.*`), tests under `backend/tests` | `src/` layout, `casewright` package, `pyproject.toml` at root |
| **Compute hosts in IaC** | Data/AI platform only — **no** container, registry, or function-app modules | Full compute: `containerenv` + `containerapp` + `functionapp` + `registry` + `identity` modules |
| **azd service deployment** | `azure.yaml` declares **infra + hooks only** (no `services:`) — app code deployed out-of-band | `azure.yaml` declares **three deployable services** (`casewright-api`, `casewright-worker`, `casewright-scheduler`) |
| **Service decomposition** | One FastAPI backend process hosts API + worker + orchestration | API, worker, scheduler are **separately deployed units** (2 Container Apps + 1 Function) |
| **Managed identities** | Broader/shared identity model | **Three** user-assigned identities (api / worker / scheduler), least-privilege per service |
| **RBAC** | Out-of-band **post-provision scripts** (`azd-postprovision-rbac.ps1/.sh`, `setup_rbac.py`, `setup_cosmos_rbac.py`) via azd hooks | **In-template** `infra/modules/rbac.bicep`, deployed atomically with resources |
| **Container registry** | Not provisioned in IaC | `registry.bicep` (ACR) provisioned; images built with `remoteBuild` |
| **OpenAI module** | Folded into `aiservices.bicep` / Foundry | Dedicated `openai.bicep` module |
| **Environments** | Single `main.parameters.json` | `dev` / `test` / `prod` `.bicepparam` files |
| **Python target** | `>=3.12` | 3.14 venv tooling (tasks/scripts) |
| **Agent orchestration code** | `backend/app/workflows/` (agent-framework executors) + richer services (incl. `pii_detection_service`) | `src/casewright/agentic/` + `retrieval/` (local hybrid fallback) |
| **Bicep modules** | 10 modules (platform-focused) | 15 modules (platform **+** compute + identity + rbac) |

---

## 3. Architecture perspective

### case-assistant-agent — platform-provisioning + single backend
- The Bicep templates provision the **data and AI platform** (Foundry, Search, Cosmos, Service
  Bus, Storage, Key Vault, AI Services, monitoring) but **not the compute hosts**. There are no
  container, registry, or function-app modules.
- `azure.yaml` contains `infra:` and `hooks:` but **no `services:` block**, so `azd up` provisions
  infrastructure and runs the RBAC hook — it does not build/push/deploy the application. The
  FastAPI backend (API + worker + orchestration in one process) is run/deployed through a separate
  path.
- Net effect: a **coarser-grained** topology where API, queue worker, and orchestration share one
  application boundary.

### casewright — full-stack, three-service, deploy-by-azd
- IaC provisions the **same platform plus the compute hosts**: a Container Apps environment and two
  Container Apps (API, worker), a Function App (scheduler), an ACR, and three user-assigned
  identities.
- `azure.yaml` declares **three deployable services**, so `azd deploy` builds and ships each unit
  independently (API + worker via remote container build; scheduler as a Python Function).
- Net effect: a **finer-grained** topology where each concern scales and deploys on its own.

**Reading of the difference:** casewright is an end-to-end, reproducible deployment unit (infra +
compute + app, one `azd` workflow). case-assistant-agent treats IaC as platform provisioning and
leaves app hosting to a separate process.

---

## 4. Design perspective

### Code structure & testability
- **casewright** uses a modern **`src/` layout** with a single root `pyproject.toml`. Concerns are
  split into clear packages — `api/`, `worker/`, `agentic/`, `retrieval/`, `ingestion/`,
  `sharepoint/`, `repositories/`, `functions/`. This maps 1:1 onto the deployable services, which
  keeps the deployment boundary and the code boundary aligned.
- **case-assistant-agent** uses a `backend/app/` package with a comparable internal breakdown
  (`api/`, `services/`, `workflows/`, `ingestion/`, `repositories/`, `agents/`). It carries some
  capabilities casewright keeps lighter, notably an explicit **`pii_detection_service`** and a
  formal **agent-framework `workflows/` (executors)** orchestration layer.

### Retrieval resilience
- Both retrieve through **Foundry IQ** at query time. casewright additionally keeps an **in-process
  hybrid + semantic query as an offline fallback** (`retrieval/query.py`, ADR-2/ADR-10), so the
  service can still answer when Foundry is not configured. This is an explicit design decision
  recorded in casewright's ADRs.

### Design intent, documented
- casewright ships **architecture decision records** (`docs/architecture-decisions.md`, ADR-1…),
  giving reviewers the "why" behind the archetype, retrieval pattern, queue, partition key, and
  identity model. This makes the design auditable in a way that is valuable for review and
  governance.

---

## 5. Operations perspective

### Deployability
- **casewright:** one `azd up` / `azd deploy` builds and ships all three services; rollouts are
  per-service. The bicep-defined registry + identities mean there is no manual wiring step.
- **case-assistant-agent:** `azd` provisions infra and grants RBAC via a hook; the application
  itself is deployed through a separate mechanism, which is more steps and more room for
  environment drift between "what IaC created" and "what is actually running."

### Security operations
- **casewright** assigns RBAC **inside the template** (`rbac.bicep`), so role assignments are
  versioned, reviewable in `what-if`, idempotent, and deployed with the resources they grant.
  Three per-service identities make least-privilege the default.
- **case-assistant-agent** assigns RBAC via **post-provision scripts**. These work, but live
  outside the deployment graph: they can be skipped, fail silently, or drift, and a broader shared
  identity widens the blast radius if a single credential is compromised.

### Scaling & cost
- Both decouple sync via Service Bus and both run the scheduler on a Function (scale-to-zero).
- casewright's **separately hosted** API and worker scale **independently** — a burst of sync work
  scales the worker without touching API capacity. In case-assistant-agent's single-process
  backend, API and worker share a host and scale together.

### Multi-environment promotion
- **casewright:** `dev` / `test` / `prod` `.bicepparam` files give clean, parameterized promotion
  out of the box.
- **case-assistant-agent:** a single `main.parameters.json`; multi-env requires additional
  parameterization.

### Known operational caveat (casewright, deployed)
- On redeploys, two settings have been observed to drift to `Disabled` by security-baseline audit
  policies and must be re-enabled: Cosmos `publicNetworkAccess` (symptom: `/api/chat/query` →
  `500 Forbidden ... Cosmos DB firewall`) and the function storage account `publicNetworkAccess`
  (symptom: scheduler deploy `403`). Documented in `docs/demo-deployed-and-teams.md` and repo
  memory. This is an artifact of the richer, fully-deployed topology — case-assistant-agent, by
  not deploying compute via IaC, simply doesn't surface these particular drift points.

---

## 6. Where each one is stronger

### Advantages of **casewright**
1. **End-to-end reproducible deployment** — infra + compute + app in one `azd` workflow; nothing is
   wired by hand.
2. **Least-privilege by construction** — three per-service identities and in-template RBAC, both
   reviewable in `what-if`.
3. **Independent scaling & rollout** — API, worker, scheduler scale and deploy separately.
4. **Multi-environment ready** — `dev`/`test`/`prod` parameter sets.
5. **Code boundary == deployment boundary** — `src/` packages map onto the deployable services.
6. **Retrieval fallback** — answers locally even without Foundry.
7. **Documented decisions** — ADRs make the design auditable.

### Advantages of **case-assistant-agent**
1. **Lower baseline complexity** — one backend process and a platform-only IaC footprint mean fewer
   moving parts to provision, deploy, and monitor (no ACR, no container env, no per-service
   identities, no firewall-drift surface).
2. **Richer in-app capabilities present today** — an explicit **PII detection** service and a
   formal **agent-framework workflows/executors** orchestration layer.
3. **Flexible hosting** — because IaC is platform-only and `azure.yaml` has no `services:`, the team
   is free to host the backend however they choose without changing the templates.
4. **Fewer deploy-time failure modes** — not deploying compute via IaC avoids the public-network /
   firewall drift that casewright must manage on redeploys.

---

## 7. Recommendation

- Choose **casewright** when the priorities are **production-grade operations**: least-privilege
  security as code, independent per-service scaling, multi-environment promotion, and a single
  reproducible `azd` deploy. The cost is more components and a couple of post-deploy drift points to
  manage.
- Choose **case-assistant-agent** when the priorities are **simplicity and in-app feature depth**
  (PII detection, explicit workflow orchestration) with **flexible, self-managed hosting**, and the
  team is comfortable deploying the application outside of IaC and managing RBAC via scripts.

Both are sound. casewright optimizes for **operability and security posture**; case-assistant-agent
optimizes for **simplicity and application-layer richness**. The right choice depends on whether the
greater value is a hardened, fully-automated deployment pipeline or a leaner footprint with deeper
in-process capabilities.
