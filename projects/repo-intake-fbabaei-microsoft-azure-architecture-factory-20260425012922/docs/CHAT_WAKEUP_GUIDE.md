# Updating a Project from GitHub Copilot Chat

Once a project exists under `projects/<slug>/`, you can request changes to it directly from GitHub Copilot Chat — without opening the portal or editing any files by hand. The orchestrator understands a small set of **wake words**, asks for what it needs, and then runs the change through the normal Update pipeline (BRD diff → architecture delta → code sync → infra delta → validation).

---

## Wake Words

Start a chat message with any of these (case-insensitive):

- `wakeup`
- `wake up`
- `wake-up`
- `hey orchestrator`
- `hey factory`
- `hey project`
- `hey` (alone, or `hey <slug>`)

A bare `hey can you explain this code` is **not** a wake word — the orchestrator ignores it. A message that looks like a project change request is.

---

## Two Ways to Use It

### 1. Conversational (easiest)

Just say hi. The orchestrator will ask for what it needs.

**You:**
```
Hey
```

**Orchestrator:**
> 👋 Hi! Orchestrator here — how can I help you?
> Tell me which project you'd like to change and what changes to apply. You can:
>   • Give me a project slug + a file path: `"project: <slug> changes: <path>"`
>   • Give me a project slug + paste the changes inline (start with `"paste:"`)
>   • Attach a file with the change request
>
> If you're not sure which project, say `"list projects"` and I'll show you.

**You** (reply in the next turn):
```
project: customer-analytics-platform
paste:
- Add a fraud detection microservice that scores every order
- Remove the legacy SMS notification service
- Tighten RBAC on the clinician portal to require MFA
```

**Orchestrator:**
- Runs the BRD diff
- Snapshots the prior architecture under `projects/<slug>/diagrams/history/`
- Updates the diagram
- Scaffolds new services, retires removed ones to `src/_removed/v<N>/`, refactors modified ones
- Applies Bicep deltas
- Re-runs validation
- Streams progress back to chat as each phase completes

### 2. One-Shot (fastest)

Put everything in the first message:

```
wakeup project: customer-analytics-platform changes: ./inbox/new-fraud-requirement.md
```

```
Hey factory — slug: eldercare-facility
paste:
- Add HIPAA audit log export every 24h
- Remove legacy SMS notifier
```

```
wake-up iot-telemetry-platform file: C:\tmp\telemetry-changes.md dry-run: true
```

---

## What You Can Say After the Wake Word

| Directive | Meaning | Required? |
|-----------|---------|-----------|
| `project: <slug>` or `slug: <slug>` or just the slug as the next word | Which project to update | Yes |
| `changes: <path>` or `file: <path>` | Path to a file containing the change request | One of these three |
| `paste:` followed by multi-line content | Inline changes pasted into chat | |
| An attached file in the chat | Same as `changes:` | |
| `mode: update` (default) | Full sync: add, refactor, retire | No |
| `mode: drift-check` | Read-only comparison of diagram vs code | No |
| `mode: sync` | Same as default update | No |
| `mode: generate` | Only scaffold added components | No |
| `mode: refactor` | Only update modified components | No |
| `dry-run: true` | Plan only — show what would change, write nothing | No |
| `deploy: true` | Redeploy to Azure after changes apply cleanly | No |

---

## Helpful Replies During the Conversation

Once the orchestrator has greeted you, these replies work:

| You say | Orchestrator does |
|---------|-------------------|
| `list projects` | Lists the first 20 project slugs under `projects/` |
| `customer-analytics-platform` (slug only) | Confirms the project exists, asks for changes |
| pastes changes (no slug yet) | Asks which project to apply them to |
| `cancel` / `never mind` / `nm` | Aborts cleanly, no files touched |

---

## Safety Rules (Good to Know)

- **Existing projects only.** Wake-up calls cannot create new projects. If you want a new project, use the portal or the standard orchestrator invocation with a BRD.
- **Never deletes.** Services removed from the architecture are moved to `projects/<slug>/src/_removed/v<N>/` — nothing is lost.
- **Snapshots everything.** The prior BRD, diagram, and notes are copied to `projects/<slug>/docs/history/` and `projects/<slug>/diagrams/history/` before anything changes.
- **`dry-run: true` writes nothing.** Use it to preview a change before committing.
- **No auto-deploy.** Wake-up updates never deploy unless you explicitly pass `deploy: true`.
- **Everything is logged** to `projects/<slug>/logs/orchestration.log` with `source: ghcp-wakeup` so portal-driven and chat-driven updates stay auditable together.

---

## Behind the Scenes

The wake-up layer only **normalizes** your chat input. It:

1. Writes your changes to `projects/<slug>/docs/requirements.md.new`
2. Creates a marker file at `projects/<slug>/.brd-update-pending.json` with `source: "ghcp-wakeup"`
3. Hands off to the existing Update Mode (Phase U0 onward)

This means a chat-driven update follows the exact same phases, same safety rules, and same outputs as a portal-driven update — just with a friendlier entry point.

---

## Where the Work Happens

The heavy lifting is done by four specialized agents coordinated by `project-orchestrator`:

| Agent | Responsibility |
|-------|----------------|
| `drawio-architecture-reader` | Inventories the current architecture |
| `brd-to-architecture-diagram` | Applies diagram deltas from the BRD diff |
| `source-code-maintainer` | Keeps code in sync: adds, refactors, retires services |
| `azure-architecture-implementer` | Scaffolds new services and applies Bicep deltas |

Plus `project-state-manager` for manifest/log bookkeeping and `bicep-infrastructure-validator` for infra validation.

---

## Troubleshooting

**"❌ No project found at projects/<slug>/"**
The slug doesn't exist. Run `list projects` to see what's available, or check the portal.

**"Ambiguous slug — did you mean..."**
Multiple projects match your partial slug. Pick one from the list.

**Orchestrator didn't respond to `hey`**
The message after `hey` looked like a normal Copilot request. Be explicit: `hey orchestrator` or `wakeup`.

**Wake-up completed but nothing changed**
The BRD diff was empty or cosmetic-only (whitespace, typos). The orchestrator short-circuits these as `no-op` updates. Check `projects/<slug>/docs/brd-diff-v<N>.md` to confirm.

---

## Related Docs

- [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) — Full project lifecycle
- [BRD_CHAT_SUBMISSION.md](BRD_CHAT_SUBMISSION.md) — Greenfield project creation from chat
- [../.github/agents/project-orchestrator.agent.md](../.github/agents/project-orchestrator.agent.md) — Full agent spec
- [../.github/agents/source-code-maintainer.agent.md](../.github/agents/source-code-maintainer.agent.md) — Code sync agent
