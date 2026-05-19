# GitHub MCP Server + AAF Integration Guide

> **TL;DR** — Register the GitHub MCP Server alongside the AAF MCP Server in
> `.vscode/mcp.json`. Then an AI agent (Copilot, Claude) can read GitHub issues,
> submit BRDs to AAF, retrieve generated artifacts, and push a PR — all in one
> conversation.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Configuration Reference](#configuration-reference)
4. [Workflow Patterns](#workflow-patterns)
   - [Pattern 1 – Issue → Project → PR](#pattern-1--issue--project--pr)
   - [Pattern 2 – PR Security Gate](#pattern-2--pr-security-gate)
   - [Pattern 3 – Bicep / Terraform Validation](#pattern-3--bicep--terraform-validation)
   - [Pattern 4 – Traceability Report on Merge](#pattern-4--traceability-report-on-merge)
5. [Automated Pipeline (GitHub Actions)](#automated-pipeline-github-actions)
6. [Available Tool Reference](#available-tool-reference)
7. [Example Prompts](#example-prompts)
8. [Security Considerations](#security-considerations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Client  (VS Code Copilot Agent Mode / Claude Desktop)  │
│                                                             │
│   ┌───────────────────┐     ┌──────────────────────────┐   │
│   │  GitHub MCP Server │     │  AAF MCP Server           │   │
│   │  (ghcr.io/github/ │     │  (localhost:8000/mcp)     │   │
│   │   github-mcp-server)│    │                          │   │
│   │                   │     │  Tools:                  │   │
│   │  Tools:           │     │  • submit_brd            │   │
│   │  • get_issue      │     │  • get_project_status    │   │
│   │  • create_branch  │     │  • get_project_artifacts │   │
│   │  • push_files     │     │  • invoke_agent          │   │
│   │  • create_pr      │◄───►│  • list_projects         │   │
│   │  • add_comment    │     │  • list_accessible_agents│   │
│   └───────────────────┘     └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
   GitHub.com / GitHub                AAF Engine
   Enterprise                         (project-orchestrator,
   (issues, PRs, branches,             bicep-validator, etc.)
    file contents)
```

The key insight is that both MCP servers are registered in the same
`.vscode/mcp.json`, so the AI agent can call tools from **both** servers in a
single conversation to bridge GitHub and AAF.

---

## Quick Start

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker Desktop | ≥ 4.x | Runs the GitHub MCP Server container |
| AAF MCP Server | running | `cd src/mcp_server && uvicorn main:app --port 8000` |
| GitHub PAT | — | Scopes: `repo`, `issues`, `pull_requests`, `contents`, `metadata` |
| VS Code | ≥ 1.99 | Copilot agent mode |

### Step 1 – Create a GitHub Personal Access Token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Create a token with:
   - **Repository access**: the AAF repository (or all repositories)
   - **Permissions**: `Issues (read/write)`, `Pull requests (read/write)`,
     `Contents (read/write)`, `Metadata (read)`
3. Copy the token — you will paste it into VS Code's prompt on first use.

### Step 2 – Verify `.vscode/mcp.json`

The file already contains the GitHub MCP Server entry:

```jsonc
{
  "servers": {
    "factory-mcp-orchestrator": {
      "url": "http://localhost:8000/mcp",
      "type": "http"
    },
    "github": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
               "ghcr.io/github/github-mcp-server"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${input:github_pat}"
      }
    }
  },
  "inputs": [
    {
      "id": "github_pat",
      "type": "promptString",
      "description": "GitHub PAT (scopes: repo, issues, pull_requests, contents, metadata)",
      "password": true
    }
  ]
}
```

When you open VS Code, the GitHub MCP Server will start automatically.  VS Code
prompts for your PAT on first use.

### Step 3 – Start the AAF MCP Server

```bash
# From the repo root
cd src/mcp_server
pip install -r ../../requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Or via Docker:

```bash
docker build -f Dockerfile.mcp-server -t aaf-mcp-server .
docker run -p 8000:8000 aaf-mcp-server
```

### Step 4 – Verify both servers in VS Code

Open the **MCP Servers** panel in VS Code (Command Palette → `MCP: List Servers`).
You should see:

```
✓ factory-mcp-orchestrator   http://localhost:8000/mcp   6 tools
✓ github                     stdio (docker)              30+ tools
✓ draw-io-mcp                http://localhost:8080/mcp   2 tools
```

---

## Configuration Reference

### `.vscode/mcp.json` (VS Code Copilot)

Already configured — see [Quick Start](#quick-start).

### `.copilot/mcp-config.json` (Claude Desktop / other clients)

Already configured with the Docker-based GitHub MCP Server entry.  Set the
environment variable before launching your client:

```bash
# Windows PowerShell
$env:GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_..."

# macOS / Linux
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_..."
```

### Alternative: `npx` (no Docker)

If you prefer not to use Docker, replace the `github` server entry with:

```jsonc
"github": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${input:github_pat}"
  }
}
```

---

## Workflow Patterns

### Pattern 1 – Issue → Project → PR

**Scenario:** A user files a GitHub issue containing product requirements.  The
AI agent reads the issue, generates a full AAF project (architecture diagram,
code, Bicep infra), and opens a PR with all generated artifacts.

**Tool sequence:**

```
github › get_issue(owner, repo, issue_number)
  └─ extract BRD text from issue.body

factory-mcp-orchestrator › submit_brd(brd_text, project_name, iac_tool)
  └─ returns { run_id, project_slug }

factory-mcp-orchestrator › get_project_status(run_id)   [poll every 30 s]
  └─ wait until status == "completed"

factory-mcp-orchestrator › get_project_artifacts(project_slug, artifact_types=["all"])
  └─ returns [{ path, content }, ...]

github › create_branch(owner, repo, "aaf/<slug>", base="main")

github › push_files(owner, repo, "aaf/<slug>", files)

github › create_pull_request(owner, repo, head="aaf/<slug>", base="main",
                              title="feat(aaf): ...", body="Closes #<N>")

github › add_issue_comment(owner, repo, issue_number, "PR opened: <url>")
```

**Example prompt:**

> "Read issue #42 in fbabaei-microsoft/azure-architecture-factory, generate an
> AAF project from it using Terraform, and open a PR."

---

### Pattern 2 – PR Security Gate

**Scenario:** A pull request modifies source code.  Before merging, run the
security compliance audit and post findings as a review comment.

**Tool sequence:**

```
github › get_pull_request(owner, repo, pr_number)
  └─ identify project slug from branch name or PR body

factory-mcp-orchestrator › invoke_agent(
    "security-compliance-auditor",
    { project_path: "projects/<slug>", "fix": false }
  )
  └─ returns severity-classified findings

github › create_review_comment(owner, repo, pr_number, body=<findings_markdown>)
```

**Example prompt:**

> "Run the AAF security audit on the changes in PR #17 and post the findings as
> a review comment."

---

### Pattern 3 – Bicep / Terraform Validation

**Scenario:** A PR modifies infrastructure files.  Validate them and post a
pass/fail status as a PR comment.

**Tool sequence:**

```
github › get_pull_request(owner, repo, pr_number)
  └─ read list of changed files

factory-mcp-orchestrator › invoke_agent(
    "bicep-infrastructure-validator",   // or terraform-infrastructure-validator
    { project_path: "projects/<slug>" }
  )
  └─ returns { valid: bool, errors: [], warnings: [] }

github › add_issue_comment(owner, repo, pr_number, body=<validation_report>)
```

**Example prompt:**

> "Validate the Bicep changes in PR #23 and comment the results."

---

### Pattern 4 – Traceability Report on Merge

**Scenario:** After a project is generated and merged, produce a requirements
traceability report and link it back to the original issue.

**Tool sequence:**

```
github › get_pull_request(owner, repo, pr_number)
  └─ read "Closes #N" to get issue_number

factory-mcp-orchestrator › invoke_agent(
    "project-traceability-advisor",
    { project_path: "projects/<slug>", "update-manifest": true }
  )
  └─ returns coverage_percentage and report path

factory-mcp-orchestrator › get_project_artifacts(project_slug,
    artifact_types=["docs"])
  └─ retrieve the traceability report markdown

github › add_issue_comment(owner, repo, issue_number, body=<coverage_summary>)
```

---

## Automated Pipeline (GitHub Actions)

The workflow `.github/workflows/aaf-generate-from-issue.yml` automates Pattern 1
without requiring a local MCP client.

### How to trigger it

1. Create a GitHub issue with a BRD in the body (see `factory-templates/` for
   templates).
2. Apply the label **`aaf:generate`** to the issue.
3. The workflow runs automatically:
   - Creates branch `aaf/issue-<N>-<slug>`
   - Commits the BRD to `docs/requirements-issue-<N>.md`
   - Opens a draft PR
   - Posts a `@copilot` work assignment comment on the PR

4. The GitHub Copilot coding agent picks up the comment and runs
   `project-orchestrator` on the BRD, committing all generated artifacts to
   the branch.

### Workflow diagram

```
GitHub Issue (labeled "aaf:generate")
        │
        ▼
aaf-generate-from-issue.yml
        │
        ├─ Create branch  aaf/issue-<N>-<slug>
        ├─ Commit BRD →   docs/requirements-issue-<N>.md
        ├─ Open draft PR  (Closes #<N>)
        └─ Post @copilot comment on PR
                │
                ▼
        GitHub Copilot coding agent
                │
                ├─ project-orchestrator runs on BRD
                ├─ Generates: architecture, code, infra, docs
                ├─ Commits everything to branch
                └─ Marks PR ready for review
```

### Required secrets / permissions

| Setting | Value |
|---------|-------|
| `GITHUB_TOKEN` permissions | `contents: write`, `issues: write`, `pull-requests: write` |
| GitHub Copilot coding agent | Must be enabled on the repository |

No additional secrets are needed — the workflow uses the built-in
`GITHUB_TOKEN`.

---

## Available Tool Reference

### GitHub MCP Server tools (selection)

| Tool | Description |
|------|-------------|
| `get_issue` | Fetch issue details, body, labels, assignees |
| `list_issues` | Search/filter issues by label, state, assignee |
| `create_issue` | Open a new issue |
| `add_issue_comment` | Post a comment on an issue or PR |
| `update_issue` | Change state, labels, assignees |
| `create_branch` | Create a new branch from a base |
| `get_file_contents` | Read any file from a branch |
| `push_files` | Commit one or more files to a branch |
| `create_pull_request` | Open a PR with title, body, head/base branches |
| `get_pull_request` | Read PR details and changed files |
| `search_code` | Full-text search across the repository |
| `list_commits` | Browse commit history on a branch |

### AAF MCP Server tools

| Tool | Description |
|------|-------------|
| `submit_brd` | Submit a BRD and start the generation pipeline |
| `get_project_status` | Poll run status (`pending / running / completed / failed`) |
| `get_project_artifacts` | Retrieve generated files by type |
| `invoke_agent` | Run any named AAF specialist agent |
| `list_accessible_agents` | List all agents available for invocation |
| `list_projects` | Search and list previously generated projects |

See `docs/MCP_SERVER.md` for the full AAF MCP tool reference with parameter
tables and response examples.

---

## Example Prompts

Copy these into VS Code Copilot agent mode with both MCP servers active.

### 1 — Generate project from issue

```
Read GitHub issue #42 in the fbabaei-microsoft/azure-architecture-factory repo,
submit its body as a BRD to AAF with iac_tool=bicep, wait for completion, then
push the generated src/ and infra/ files to a new branch and open a draft PR
that closes #42.
```

### 2 — Security review on PR

```
Run the AAF security-compliance-auditor against the project referenced in PR #17
(fbabaei-microsoft/azure-architecture-factory) and post the severity-classified
findings as a review comment on the PR.
```

### 3 — Validate Bicep before merge

```
Get the list of .bicep files changed in PR #23 of
fbabaei-microsoft/azure-architecture-factory, invoke the
bicep-infrastructure-validator on that project, and add a comment to the PR
with a pass/fail summary and any errors found.
```

### 4 — List open AAF projects and link them to issues

```
List all AAF projects in status "completed" and, for each one that has a
project-slug starting with "issue-", find the corresponding GitHub issue in
fbabaei-microsoft/azure-architecture-factory and add a comment with the
generated artifacts summary.
```

### 5 — End-to-end from freeform requirements

```
I want to build a Python REST API that stores IoT sensor readings in Azure
Cosmos DB and exposes a dashboard with Azure Static Web Apps. Use Bicep for
infrastructure. Generate the AAF project and push it to a new branch called
aaf/iot-dashboard in fbabaei-microsoft/azure-architecture-factory, then open
a PR.
```

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| PAT stored in VS Code secret store | VS Code encrypts inputs marked `"password": true`; never commit the PAT to source |
| GitHub MCP Server container access | Container runs with `--rm`; no persistent state outside the token scope |
| AAF MCP Server exposes agent invocation | Bind to `127.0.0.1` only; do not expose port 8000 publicly without authentication |
| `push_files` writes to GitHub | Always confirms target repository; never writes to `main`/`dev`/`preview` directly |
| Issue body as BRD | BRD text is validated (≤ 200 K chars, no path traversal) before being passed to `submit_brd` |
| Generated artifacts pushed to GitHub | Filter out `tmp/`, `outputs/`, and any file containing env-var patterns before push |

---

## Troubleshooting

### `github` server not listed in Copilot tools

- Verify Docker Desktop is running: `docker ps`
- Pull the image manually: `docker pull ghcr.io/github/github-mcp-server`
- Reload VS Code (Command Palette → `Developer: Reload Window`)

### PAT permission denied

- Confirm the PAT has `Contents: Read and write` and `Pull requests: Read and write`
- Fine-grained PATs need explicit repository access — "All repositories" or the
  specific repo

### AAF MCP Server unreachable

- Confirm the server is running: `curl http://localhost:8000/health`
- Check for port conflicts: `netstat -an | findstr 8000`
- See `docs/MCP_SERVER.md` for server startup details

### `submit_brd` returns `validation_failed`

- The BRD must contain at least a project name and description
- Maximum 200 000 characters
- `iac_tool` must be `bicep` or `terraform`
