# Error-Handling Gate — csa-helper-runtime

Iterations executed: **1**. Final status: **passed**. `critical = 0`, `major = 0`, `minor = 0`. Services audited: **1** (`api`).

## Contract Coverage

| Requirement | Where |
|---|---|
| Validate inputs at the boundary | `AskRequest(prompt: str = Field(..., min_length=1, max_length=8000))` |
| Surface 4xx for client errors | Pydantic raises 422 on bad body; `/health/ready` returns 503 with `{missing_env}` when config is bad |
| Surface 5xx for server errors with structured detail | `HTTPException(500, {"error": str(exc)})` in `/ask`; `503 {"team_init": ...}` when the team can't initialize |
| Never leak secrets in error bodies | The only env surfaced in errors is the *names* of missing keys, never values |
| Telemetry on every request, even failures | Logger configured; App Insights wiring is best-effort and degrades silently if disabled |
| Lazy / deferred init avoids crash-on-boot | `_init_team()` deferred; startup is best-effort, `/health/ready` is the source of truth |
| Hand-off depth bound | Inherited from `build_team.ask` (`max 6 hand-offs`) — preserves FR-3 (no upstream changes) |

## Notes
- Upstream `build_team.ask` already returns a sentinel string when max hand-off depth is reached; the wrapper does not alter that contract per FR-3.
