-- Factory template: chat / session persistence on Azure SQL.
-- Idempotent — safe to re-run against an existing database.
--
-- Use when a project's BRD calls for resilient multi-turn interactions
-- (chat, conversational extraction, agent loops). Apply once per env:
--
--   sqlcmd -S "<server>.database.windows.net" -d "<db>" -G \
--          -i ./infra/sql/sessions.sql
--
-- AAD authentication is assumed; do not embed SQL logins.
--
-- Schema notes:
--   * Sessions.SessionId is a string PK (GUID-N or app-defined) so the
--     application owns id allocation.
--   * Status is enforced in application code (see SessionStatus state
--     machine in the .NET / Python implementer outputs).
--   * SessionTurns.TurnIndex is monotonic per session and is computed
--     server-side via MAX(TurnIndex)+1 in a single batch with the INSERT
--     to remain durable across reconnects and process restarts.

IF OBJECT_ID('dbo.Sessions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Sessions (
        SessionId        NVARCHAR(64)   NOT NULL PRIMARY KEY,
        OwnerId          NVARCHAR(128)  NOT NULL,
        Status           NVARCHAR(32)   NOT NULL,
        CreatedAtUtc     DATETIMEOFFSET NOT NULL,
        UpdatedAtUtc     DATETIMEOFFSET NOT NULL,
        LastActivityUtc  DATETIMEOFFSET NOT NULL
    );

    CREATE INDEX IX_Sessions_OwnerId_Status
        ON dbo.Sessions (OwnerId, Status);
END;

IF OBJECT_ID('dbo.SessionTurns', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.SessionTurns (
        TurnId        BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        SessionId     NVARCHAR(64)         NOT NULL,
        TurnIndex     INT                  NOT NULL,
        Role          NVARCHAR(20)         NOT NULL,    -- 'user' | 'agent'
        Content       NVARCHAR(MAX)        NOT NULL,
        CreatedAtUtc  DATETIMEOFFSET       NOT NULL,
        CONSTRAINT FK_SessionTurns_Sessions
            FOREIGN KEY (SessionId) REFERENCES dbo.Sessions(SessionId)
    );

    CREATE INDEX IX_SessionTurns_SessionId_TurnIndex
        ON dbo.SessionTurns (SessionId, TurnIndex);
END;
