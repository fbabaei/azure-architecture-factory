# GitHub MCP Server — Use Cases

A practical catalogue of what you can do with the GitHub MCP Server from an AI
agent (VS Code Copilot, Claude Desktop, or any MCP-compatible client). Each use
case lists the tools involved, a ready-to-paste prompt, and the expected
outcome.

> **Setup prerequisite** — The GitHub MCP Server must be running and your PAT
> configured. See [GITHUB_MCP_QUICKSTART.md](./GITHUB_MCP_QUICKSTART.md) to be
> up and running in 5 minutes.

---

## Contents

1. [Issue Management](#1-issue-management)
2. [Code Review & Pull Requests](#2-code-review--pull-requests)
3. [Repository Exploration](#3-repository-exploration)
4. [Project Generation with AAF](#4-project-generation-with-aaf)
5. [Documentation Automation](#5-documentation-automation)
6. [Release & Changelog Management](#6-release--changelog-management)
7. [Security & Compliance Gates](#7-security--compliance-gates)
8. [Multi-Repository Operations](#8-multi-repository-operations)
9. [AI-Assisted Development](#9-ai-assisted-development)

---

## 1. Issue Management

### 1.1 Triage a backlog of open issues

**When to use:** You have accumulated many unlabelled issues and want to
categorise and prioritise them automatically.

**Tools:** `list_issues`, `get_issue`, `update_issue`

**Prompt:**
```
List all open issues in fbabaei-microsoft/azure-architecture-factory that have
no labels. For each one, read the body, infer the most appropriate label from
[bug, enhancement, documentation, question, aaf:generate], and apply it.
Summarise what you labelled and why.
```

**Outcome:** All unlabelled issues receive a label; a summary table is returned.

---

### 1.2 Create issues from a TODO list in code

**When to use:** You have `// TODO:` comments scattered across a codebase that
should be tracked as GitHub issues.

**Tools:** `search_code`, `create_issue`

**Prompt:**
```
Search for all TODO comments in the src/ directory of
fbabaei-microsoft/azure-architecture-factory. For each unique TODO, create a
GitHub issue with the file path, line reference, and the TODO text as the body.
Add the label "tech-debt". Return a list of created issue URLs.
```

**Outcome:** Each TODO becomes a trackable issue linked to the file location.

---

### 1.3 Close resolved issues automatically

**When to use:** A batch of bug-fix PRs has been merged; you want to close the
issues they reference.

**Tools:** `list_commits`, `update_issue`, `add_issue_comment`

**Prompt:**
```
Look at the last 20 commits on main in fbabaei-microsoft/azure-architecture-factory.
Find any commits whose message contains "Fixes #N" or "Closes #N". For each such
issue number, close the issue and post a comment: "Auto-closed: resolved in
commit <sha> — <commit message>."
```

**Outcome:** Resolved issues are closed with a traceable comment.

---

### 1.4 Summarise a sprint's issues into a report

**When to use:** End of sprint; you need a status summary for stakeholders.

**Tools:** `list_issues`, `get_issue`

**Prompt:**
```
List all issues in fbabaei-microsoft/azure-architecture-factory that were
closed in the last 14 days. Group them by label. For each group, write a
2-sentence summary of what was accomplished. Format the output as a markdown
report I can paste into a Confluence page.
```

**Outcome:** A stakeholder-ready markdown sprint report.

---

## 2. Code Review & Pull Requests

### 2.1 Understand what a PR does before reviewing

**When to use:** You've been assigned a large PR and want a plain-English
summary before diving into the diff.

**Tools:** `get_pull_request`, `get_pull_request_diff`, `get_file_contents`

**Prompt:**
```
Summarise PR #34 in fbabaei-microsoft/azure-architecture-factory. Explain:
1. What problem it solves (based on linked issues and description).
2. Which files are changed and why.
3. Any potential risks or areas that need careful review.
```

**Outcome:** A structured PR briefing in under 30 seconds.

---

### 2.2 Post an automated code-quality checklist

**When to use:** You want a consistent review checklist on every PR before a
human reviewer looks at it.

**Tools:** `get_pull_request`, `get_file_contents`, `add_issue_comment`

**Prompt:**
```
Review PR #34 in fbabaei-microsoft/azure-architecture-factory against this
checklist and post your findings as a PR comment:
- [ ] No hardcoded credentials or secrets
- [ ] No TODO comments left in new code
- [ ] All new public functions have docstrings
- [ ] New Bicep/Terraform resources have @description annotations
- [ ] Test files updated alongside source files
```

**Outcome:** A pre-populated review checklist posted on the PR.

---

### 2.3 Suggest reviewers based on file ownership

**When to use:** You want to auto-assign reviewers to a PR based on who last
touched the changed files.

**Tools:** `get_pull_request`, `list_commits`, `update_pull_request`

**Prompt:**
```
For PR #34 in fbabaei-microsoft/azure-architecture-factory, look at the
changed files and find who committed most recently to each file. Suggest the top
3 reviewers and explain your reasoning. Then request their review if they are
different from the current reviewers.
```

**Outcome:** Reviewers assigned based on code ownership signals.

---

### 2.4 Merge conflict pre-check

**When to use:** Before merging a long-lived feature branch, you want to know
which files are likely to conflict with `main`.

**Tools:** `get_pull_request`, `get_file_contents`, `list_commits`

**Prompt:**
```
PR #34 targets main in fbabaei-microsoft/azure-architecture-factory. Look at
the files it modifies and also look at commits on main in the last 7 days that
touch the same files. Identify any likely merge conflicts and explain what they
are.
```

**Outcome:** A pre-merge conflict risk report.

---

## 3. Repository Exploration

### 3.1 Understand a codebase you've never seen

**When to use:** You've just been added to a project and need to get oriented
quickly.

**Tools:** `get_file_contents`, `list_directory`, `search_code`

**Prompt:**
```
Give me an orientation to fbabaei-microsoft/azure-architecture-factory.
Read the README, list the top-level directories, and for each directory explain
its purpose in one sentence. Then identify the main entry points for
(a) the portal, (b) the MCP server, and (c) the test suite.
```

**Outcome:** A structured onboarding summary with purpose and entry points.

---

### 3.2 Find all usages of a deprecated function

**When to use:** You've deprecated an internal function and want to know every
call site before removing it.

**Tools:** `search_code`

**Prompt:**
```
Search for all usages of the function `load_project_manifest` in
fbabaei-microsoft/azure-architecture-factory. List each file, line number, and
the surrounding 3 lines of context. Tell me which usages are safe to update
automatically.
```

**Outcome:** A complete call-site inventory for the deprecated function.

---

### 3.3 Audit for secrets accidentally committed

**When to use:** A security scan flagged potential secrets in the repository.

**Tools:** `search_code`

**Prompt:**
```
Search fbabaei-microsoft/azure-architecture-factory for patterns that look like
accidentally committed secrets: strings matching `sk-`, `ghp_`, `AKIA`,
`-----BEGIN`, or `password =`. For each match, show the file and line and
classify the severity (real secret, test fixture, or false positive).
```

**Outcome:** A prioritised list of potential secret exposures to investigate.

---

### 3.4 Track dependency drift across branches

**When to use:** Multiple long-lived branches have diverged and you need to
reconcile dependency versions.

**Tools:** `get_file_contents`

**Prompt:**
```
Read the requirements.txt (or package.json) from the main branch and from the
feat/agent-foundry-capabilities branch of
fbabaei-microsoft/azure-architecture-factory. Show me a diff of the
dependencies — which are added, removed, or version-changed.
```

**Outcome:** A clear dependency delta between branches.

---

## 4. Project Generation with AAF

> These use cases combine GitHub MCP tools with the **AAF MCP Server** tools
> (`submit_brd`, `get_project_artifacts`, `invoke_agent`). Both servers must be
> active. See [GITHUB_MCP_INTEGRATION.md](./GITHUB_MCP_INTEGRATION.md) for
> the full architecture.

### 4.1 Issue → full Azure project → PR  *(flagship workflow)*

**When to use:** A product issue contains requirements; you want a complete
Azure project generated and delivered as a PR without manual steps.

**Tools (GitHub):** `get_issue`, `create_branch`, `push_files`,
`create_pull_request`, `add_issue_comment`  
**Tools (AAF):** `submit_brd`, `get_project_status`, `get_project_artifacts`

**Prompt:**
```
Read issue #42 in fbabaei-microsoft/azure-architecture-factory.
Submit its body to AAF as a BRD with iac_tool=bicep.
Wait for the pipeline to complete (poll get_project_status every 30 s).
Retrieve all generated artifacts.
Create branch aaf/issue-42-<slug>, push the src/ and infra/ files,
and open a draft PR with title "feat(aaf): <project name>" that closes #42.
Post a comment on the issue with the PR link.
```

**Outcome:** A complete generated Azure project lands in GitHub as a PR in
under 5 minutes.

---

### 4.2 Regenerate a project after requirements change

**When to use:** A stakeholder updated the issue with new requirements after the
first generation run.

**Tools (GitHub):** `get_issue`, `get_file_contents`, `push_files`  
**Tools (AAF):** `submit_brd`, `get_project_status`, `get_project_artifacts`

**Prompt:**
```
Issue #42 in fbabaei-microsoft/azure-architecture-factory has been updated.
Re-read the current body, submit an updated BRD to AAF, wait for completion,
then update the existing branch aaf/issue-42-<slug> with the new generated
files. Comment on the issue: "Project regenerated from updated requirements —
see <PR URL>."
```

**Outcome:** PR branch updated with regenerated artifacts; stakeholder notified.

---

### 4.3 Generate AAF project from freeform chat

**When to use:** A user describes what they want to build in plain language;
no issue exists yet.

**Tools (GitHub):** `create_issue`, `create_branch`, `push_files`,
`create_pull_request`  
**Tools (AAF):** `submit_brd`, `get_project_status`, `get_project_artifacts`

**Prompt:**
```
I want to build a Python FastAPI service that reads messages from Azure Service
Bus, processes them with Azure OpenAI, and stores results in Cosmos DB. Use
Terraform for IaC. Generate the full AAF project, create a tracking issue in
fbabaei-microsoft/azure-architecture-factory with the project description, then
push the generated code to a new branch and open a PR that closes the new issue.
```

**Outcome:** Issue created → project generated → PR opened, end-to-end.

---

## 5. Documentation Automation

### 5.1 Auto-generate a CHANGELOG from commit history

**When to use:** You need a changelog for an upcoming release.

**Tools:** `list_commits`, `push_files`

**Prompt:**
```
List all commits on main in fbabaei-microsoft/azure-architecture-factory since
the tag v1.0.0. Group them by conventional commit type (feat, fix, docs, chore).
Generate a CHANGELOG.md entry for version 1.1.0 dated today.
Push the updated CHANGELOG.md to the release/1.1.0 branch.
```

**Outcome:** A populated CHANGELOG.md committed to the release branch.

---

### 5.2 Sync a README with recent project changes

**When to use:** The README is stale; you want it refreshed based on recent
commits and the current folder structure.

**Tools:** `get_file_contents`, `list_commits`, `push_files`

**Prompt:**
```
Read the current README.md and the last 30 commits on main in
fbabaei-microsoft/azure-architecture-factory. Identify sections of the README
that are outdated based on the commit messages. Rewrite those sections and push
the updated README.md directly to main with commit message
"docs: sync README with recent changes".
```

**Outcome:** README updated and committed without leaving the chat.

---

### 5.3 Generate API documentation from code

**When to use:** A new API module was added without documentation.

**Tools:** `search_code`, `get_file_contents`, `push_files`

**Prompt:**
```
Find all Python files in src/mcp_server/ of
fbabaei-microsoft/azure-architecture-factory that define FastAPI routes
(look for @app.get, @app.post, etc.). For each route, extract the path,
method, docstring, and parameters. Generate a docs/API_REFERENCE.md file and
push it to the feat/agent-foundry-capabilities branch.
```

**Outcome:** A generated API reference document pushed to the feature branch.

---

## 6. Release & Changelog Management

### 6.1 Create a GitHub release with auto-generated notes

**When to use:** A milestone is complete and you want a polished release.

**Tools:** `list_commits`, `list_issues`, `create_release` (if available),
`push_files`

**Prompt:**
```
For fbabaei-microsoft/azure-architecture-factory, list all issues closed since
2026-04-01 and all commits since tag v1.0.0. Write release notes for v1.1.0:
- A one-paragraph summary of the release theme
- A "What's New" section (features)
- A "Bug Fixes" section
- A "Breaking Changes" section (if any)
Format as GitHub release notes markdown.
```

**Outcome:** Release notes ready to paste (or push) to a GitHub release.

---

### 6.2 Tag a release commit

**When to use:** You want to create an annotated git tag via the API without
leaving the agent conversation.

**Tools:** `list_commits`, `push_files`

**Prompt:**
```
Find the most recent commit on main in fbabaei-microsoft/azure-architecture-factory
that has "release" in its message. Return its SHA and a proposed semantic version
tag based on the CHANGELOG. Create a tag reference for that commit.
```

---

## 7. Security & Compliance Gates

### 7.1 Block a merge if secrets are detected

**When to use:** A PR modifies files that could introduce secrets; you want an
automated pre-merge check.

**Tools:** `get_pull_request`, `get_file_contents`, `add_issue_comment`

**Prompt:**
```
PR #34 in fbabaei-microsoft/azure-architecture-factory is targeting main.
Read every file it changes. Check for hardcoded secrets (patterns: API keys,
connection strings, PATs, passwords). If any are found, post a blocking
comment on the PR with the exact file, line, and recommended remediation. If
none are found, post "✅ Secret scan passed — no hardcoded credentials detected."
```

**Outcome:** Immediate, in-PR secret detection feedback.

---

### 7.2 Validate IaC files before merging

**When to use (AAF):** A PR modifies Bicep or Terraform; you want validation
results posted to the PR.

**Tools (GitHub):** `get_pull_request`, `add_issue_comment`  
**Tools (AAF):** `invoke_agent`

**Prompt:**
```
PR #23 in fbabaei-microsoft/azure-architecture-factory modifies infra/ files.
Invoke the bicep-infrastructure-validator on the project referenced by this PR.
Post a comment with: validation status (pass/fail), number of errors, number of
warnings, and the top 3 issues (if any).
```

**Outcome:** IaC validation results surfaced directly on the PR.

---

### 7.3 Security audit on a generated project

**When to use (AAF):** Before approving a generated project PR for merge.

**Tools (GitHub):** `get_pull_request`, `create_review_comment`  
**Tools (AAF):** `invoke_agent`

**Prompt:**
```
Run the AAF security-compliance-auditor (fix: false) on the project referenced
in PR #17 of fbabaei-microsoft/azure-architecture-factory. Post the
severity-classified findings as an inline review comment. Include counts per
severity (Critical / High / Medium / Low).
```

---

## 8. Multi-Repository Operations

### 8.1 Mirror documentation across repos

**When to use:** A shared doc (e.g., contribution guide, coding standards) must
stay in sync across multiple repositories.

**Tools:** `get_file_contents`, `push_files`

**Prompt:**
```
Read CONTRIBUTING.md from fbabaei-microsoft/azure-architecture-factory on main.
Push the same content to fbabaei/azure-architecture-factory on main
(only if the content differs). Report whether an update was needed and
what changed.
```

**Outcome:** Cross-repository doc sync with a change audit.

---

### 8.2 Cross-repo dependency audit

**When to use:** Multiple repositories share a common library and you need to
know which are on outdated versions.

**Tools:** `get_file_contents`

**Prompt:**
```
Check the version of the `azure-identity` package used in:
- fbabaei-microsoft/azure-architecture-factory (requirements.txt)
- fbabaei-microsoft/compliance-agent (requirements.txt or .csproj)
Compare against the latest release on PyPI / NuGet. Report which repos need
upgrading and by how many versions they are behind.
```

**Outcome:** A multi-repo dependency health report.

---

## 9. AI-Assisted Development

### 9.1 Generate a feature branch with implementation

**When to use:** You have a clear spec for a small feature and want the agent to
write the code AND push it.

**Tools:** `get_file_contents`, `create_branch`, `push_files`

**Prompt:**
```
In fbabaei-microsoft/azure-architecture-factory, create a branch
feat/add-project-export. Read the existing project_state_manager module in
scripts/. Add a new function `export_project_to_zip(project_slug: str) -> Path`
that zips the project folder and returns the path. Follow the existing code style.
Push the updated file to the new branch. Do not open a PR yet.
```

**Outcome:** Feature branch with implementation committed in one prompt.

---

### 9.2 Generate tests for existing code

**When to use:** A module lacks unit tests; you want them generated and pushed.

**Tools:** `get_file_contents`, `search_code`, `push_files`

**Prompt:**
```
Read the file src/mcp_server/routes/projects.py in
fbabaei-microsoft/azure-architecture-factory. Generate comprehensive pytest
unit tests for all route handlers, including happy paths and error cases.
Use `httpx.AsyncClient` for async tests and mock any database calls.
Push the new test file to tests/unit/test_projects_routes.py on the
feat/agent-foundry-capabilities branch.
```

**Outcome:** Unit tests generated and committed without leaving VS Code.

---

### 9.3 Refactor a module and open a PR

**When to use:** A module has grown too large and needs splitting; you want the
agent to do the refactor.

**Tools:** `get_file_contents`, `create_branch`, `push_files`,
`create_pull_request`

**Prompt:**
```
The file scripts/project_utils.py in fbabaei-microsoft/azure-architecture-factory
is too large. Read it, then split it into:
- scripts/project_io.py   (file read/write helpers)
- scripts/project_state.py (state machine helpers)
- scripts/project_utils.py (keep only the public API, re-exporting from above)
Create branch refactor/split-project-utils, push all three files, and open a PR
with title "refactor: split project_utils into focused modules".
```

**Outcome:** A clean refactoring PR without manual file manipulation.

---

### 9.4 Full-cycle: spec → code → PR → CI check

**When to use:** You want to go from a one-liner description to a merged-ready
PR with a passing CI status.

**Tools:** `create_issue`, `create_branch`, `push_files`,
`create_pull_request`, `get_pull_request`, `list_workflow_runs`

**Prompt:**
```
Feature: add a /version endpoint to the AAF MCP server that returns the current
package version from pyproject.toml.

In fbabaei-microsoft/azure-architecture-factory:
1. Create a tracking issue for this feature.
2. Create branch feat/version-endpoint.
3. Read src/mcp_server/main.py and add the /version endpoint following the
   existing route style. Also update pyproject.toml to bump the patch version.
4. Push the changes and open a PR that closes the issue.
5. Wait 60 seconds, then check the latest CI workflow run on the branch and
   report its status.
```

**Outcome:** End-to-end feature delivery with CI feedback in one conversation.

---

## Quick Reference — Tool × Use-Case Matrix

| Use case category | Key GitHub MCP tools | Key AAF MCP tools |
|-------------------|---------------------|-------------------|
| Issue management | `list_issues`, `update_issue`, `add_issue_comment`, `create_issue` | — |
| Code review | `get_pull_request`, `get_pull_request_diff`, `create_review_comment` | `invoke_agent` |
| Repo exploration | `search_code`, `get_file_contents`, `list_directory` | — |
| Project generation | `create_branch`, `push_files`, `create_pull_request` | `submit_brd`, `get_project_status`, `get_project_artifacts` |
| Documentation | `get_file_contents`, `push_files`, `list_commits` | — |
| Release management | `list_commits`, `list_issues`, `push_files` | — |
| Security gates | `get_pull_request`, `get_file_contents`, `add_issue_comment` | `invoke_agent` (security-compliance-auditor) |
| Multi-repo ops | `get_file_contents`, `push_files` (across repos) | — |
| AI development | `create_branch`, `push_files`, `create_pull_request` | `invoke_agent` |

---

> **See also**
> - [GITHUB_MCP_QUICKSTART.md](./GITHUB_MCP_QUICKSTART.md) — 5-minute setup
> - [GITHUB_MCP_INTEGRATION.md](./GITHUB_MCP_INTEGRATION.md) — full AAF integration guide
> - [MCP_SERVER.md](./MCP_SERVER.md) — AAF MCP Server tool reference
