# Factory SQL templates

Reusable, **idempotent** Azure SQL DDL fragments for factory projects. Copy
the relevant `.sql` file into a project's `infra/sql/` folder and apply with
`sqlcmd -G` (AAD auth) — never embed SQL logins.

| Template | Purpose | When to use |
|---|---|---|
| `sessions.sql` | `dbo.Sessions` + `dbo.SessionTurns` for chat / multi-turn agents. | BRD requires resilient conversation state across reconnects or process restarts. |

Conventions:

- All scripts are guarded with `IF OBJECT_ID('dbo.X','U') IS NULL` so re-runs are safe.
- Identifiers and primary keys are application-owned strings or `IDENTITY` columns (no `NEWID()` defaults).
- Timestamps are `DATETIMEOFFSET` (UTC, with offset) — never `DATETIME`.
- No SQL logins. Assume AAD-only auth on the target server.
