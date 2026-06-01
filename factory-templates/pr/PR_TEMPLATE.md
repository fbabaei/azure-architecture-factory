# Pull Request Body Template

Used by `project-orchestrator`, `repo-change-agent`, and any agent opening a
PR on behalf of a factory project. Write the rendered body to
`docs/PR_<TOPIC>.md` inside the project, then open the PR with:

```powershell
gh pr create --repo <owner>/<repo> --base main --head <fork>:<branch> `
  --title "feat(issue-N): <short description>" `
  --body-file docs/PR_<TOPIC>.md
```

One PR == one focused change. Prefer a single `feat(issue-N): …` commit.

---

## Description
<one-paragraph summary of the change and why it exists>

## Related Issue
Fixes #<N>

## What Changed
- **<Area>** — <file or module>: <one-line summary>
- ...

## Requirements Coverage
| Requirement (from BRD / issue) | Implementation | Validated by |
| --- | --- | --- |
| <REQ-ID or natural-language requirement> | `<file path or module>` | `<test name or build step>` |

## Files Changed
- `<path>`
- ...

## Validation
- `<build command>` — <result, e.g., 0 warnings, 0 errors>
- `<test command>` — <result, e.g., N/N passing>
- <other verification steps>

## Scope
- <what is intentionally NOT included, with a one-line rationale per item>

## Checklist
- [ ] Targets the project's declared runtime (e.g., .NET 8 LTS, Python 3.11).
- [ ] No secrets, no SQL logins, no connection strings with credentials in source.
- [ ] AAD / managed identity used for all Azure access.
- [ ] Idempotent infra (Bicep / SQL DDL with `IF OBJECT_ID` guards).
- [ ] Build clean, tests green; results pasted in **Validation**.
- [ ] BRD / architecture diagram still in sync (or updated in the same PR).
