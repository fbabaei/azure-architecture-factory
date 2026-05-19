# Guide Me Detailed Architecture

Companion notes for `guide-me-detailed-architecture.drawio`.

## Diagram Pages

1. `Guide Me - Logical Architecture`
2. `Guide Me - Sequence Flows`
3. `Guide Me - Failure Paths`

## Components and Responsibilities

- **Project Card Guide Me Link** (`factory-portal.html`): Entry point from each project tile.
- **Delegation Shim** (`openWorkflowGuideInCopilot`): Routes to tiered menu while preserving legacy fallback behavior.
- **Guide Me Modal Controller** (`scripts/portal/guide_me_menu.js`): Builds menu UI, checks report availability, and handles all action buttons.
- **Documentation Preview Renderer** (`openDocumentationPreview`): Fetches markdown and renders it as HTML in modal.
- **Refresh API Endpoint** (`POST /api/guide/refresh`): Auth-guarded route for report regeneration and metadata patching.
- **Guide Report Generator** (`scripts/generate_guide_report.py`): Deterministic analyzer that writes `docs/guide-report.md` and counts by severity.
- **Project Manifest** (`project-manifest.json`): Stores `guide_report` state for the project.
- **Factory Feed** (`factory-projects.generated.json`): Stores `guideReport` and `links.guideReport` consumed by portal cards.

## Flow Mapping

### Flow A - Report-only path

1. User clicks Guide Me.
2. User selects **View report**.
3. Portal calls `openDocumentationPreview(path, title)`.
4. Markdown is fetched from `projects/<slug>/docs/guide-report.md`.
5. Markdown is rendered in-doc modal.

### Flow B - Live guide in vscode.dev

1. User selects **Run live guide in vscode.dev**.
2. Prompt is generated and copied to clipboard.
3. Browser opens `vscode.dev` repository URL.
4. User pastes prompt in Copilot Chat agent mode.

### Flow C - Live guide in VS Code desktop

1. User selects **Run live guide in VS Code Desktop**.
2. Prompt is generated and copied to clipboard.
3. Browser opens `vscode://GitHub.copilot-chat/chat?...`.
4. Desktop Copilot Chat opens with prefilled query.

### Flow D - Refresh report mutation

1. User clicks **Refresh report**.
2. Portal posts slug to `/api/guide/refresh`.
3. Server validates auth and slug.
4. Server runs `generate_guide_report(project_root)`.
5. Server writes report markdown and patches manifest/feed.
6. Portal receives `guideReport` payload and refreshes local cache.

### Flow E - Failure and fallback behavior

1. If report metadata is missing, the portal performs `HEAD projects/<slug>/docs/guide-report.md`.
2. If `HEAD` returns 404, View report stays unavailable while live guide options remain usable.
3. If refresh fails auth (`401/403`), UI shows `Refresh failed` and keeps modal open.
4. If slug resolution fails (`404`), UI shows `Project not found`.
5. If generator raises (`500`), UI shows `Refresh failed` and leaves previous cached report untouched.
6. If refresh succeeds (`200`), UI updates cache and reopens modal with new counts/timestamp.

## Data Contracts

Expected guide report payload shape:

```json
{
  "path": "projects/<slug>/docs/guide-report.md",
  "generated_at": "2026-04-16T12:34:56Z",
  "severity_counts": {
    "critical": 0,
    "warning": 0,
    "advisory": 0,
    "ok": 0
  }
}
```

## Security and Guardrails

- Refresh endpoint is mutation-protected using `_require_auth_for_mutation()`.
- Slug is path-safe validated and resolved under `projects/` only.
- Updates are constrained to:
  - `projects/<slug>/docs/guide-report.md`
  - `projects/<slug>/project-manifest.json`
  - `factory-projects.generated.json`
