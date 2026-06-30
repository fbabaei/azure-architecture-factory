# Casewright Demo Guide — Deployed API & Teams (M365 Agents Playground)

This guide shows how to:

1. **Run queries against the deployed Casewright API** (curl, PowerShell, Swagger UI, browser).
2. **Run and test the interactive Teams bot locally** using the **Microsoft 365 Agents Playground** against the deployed backend.

> Environment used in this guide
> - Subscription: `729fcdbd-c547-48df-a749-dbee6cdb50b0`
> - Resource group: `rg-casewright-dev` (region `eastus2`)
> - Live API base URL: `https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io`

---

## Part 1 — Query the deployed API

### 1.1 Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/chat/query` | Agentic RAG query (grounded answer + citations) |
| `GET`  | `/api/chat/{conversation_id}` | Fetch a stored conversation |
| `GET`  | `/api/sharepoint/sites` | List indexed SharePoint sites |
| `GET`  | `/docs` | Swagger UI (interactive) |
| `GET`  | `/redoc` | ReDoc API reference |
| `GET`  | `/openapi.json` | OpenAPI schema |

### 1.2 Request schema for `POST /api/chat/query`

```jsonc
{
  "query": "What is the dispute in case CW-2024-0182?", // required, 1–2000 chars
  "session_id": "11111111-1111-1111-1111-111111111111", // required, MUST be a valid UUID
  "user_id": "demo-user",                                // optional
  "filters": { "site_id": "<sharepoint-site-id>" },     // optional, scope to a site
  "chat_history": []                                      // optional, prior turns
}
```

Response (abbreviated):

```jsonc
{
  "answer": "The dispute in case CW-2024-0182 involves Northwind Logistics ...",
  "citations": [
    { "document_title": "northwind-v-contoso.md", "content": "...", "page_number": null }
  ],
  "document_count": 1,
  "session_id": "11111111-1111-1111-1111-111111111111",
  "thought_process": [ /* per-attempt reasoning */ ],
  "search_history": [ /* queries the agent ran */ ],
  "attempts": 2,
  "timestamp": "..."
}
```

> **Important:** `session_id` is **required** and must be a valid UUID. Omitting it returns
> `422 session_id Field required`.

### 1.3 Quick health check

```powershell
Invoke-RestMethod -Uri "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io/api/health"
# -> { status = ok; service = casewright-api }
```

### 1.4 Run a query — PowerShell (recommended on Windows)

`Invoke-RestMethod` avoids the JSON-quoting pitfalls of `curl` in PowerShell:

```powershell
$base = "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io"

$body = @{
  query      = "What is the dispute in case CW-2024-0182?"
  session_id = [guid]::NewGuid().ToString()
} | ConvertTo-Json

Invoke-RestMethod -Uri "$base/api/chat/query" -Method Post `
  -ContentType "application/json" -Body $body |
  Select-Object answer, document_count, @{n='sources';e={$_.citations.document_title}}
```

### 1.5 Run a query — curl (use a body file)

In PowerShell, single-quoted JSON with `\"` is sent literally and breaks the request
(`400 JSON decode error`). The reliable pattern is to put the body in a file:

```powershell
@'
{ "query": "What is the dispute in case CW-2024-0182?",
  "session_id": "11111111-1111-1111-1111-111111111111" }
'@ | Set-Content -Encoding utf8 body.json

curl.exe -s -X POST `
  "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io/api/chat/query" `
  -H "Content-Type: application/json" `
  -d "@body.json"
```

On macOS/Linux (bash), inline JSON works directly:

```bash
curl -s -X POST \
  "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the dispute in case CW-2024-0182?","session_id":"11111111-1111-1111-1111-111111111111"}'
```

### 1.6 Run a query — Swagger UI (no terminal)

1. Open `https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io/docs`.
2. Expand **agentic-chat → POST `/api/chat/query`**.
3. Click **Try it out**.
4. Paste a request body (include a valid `session_id` UUID) and click **Execute**.
5. Read the grounded answer and citations in the **Response body**.

### 1.7 Expected demo result

For `What is the dispute in case CW-2024-0182?` the API returns a grounded answer about
**Northwind Logistics v. Contoso Freight** (breach of a freight services agreement, 38 missed
shipments, ~$1.2M in losses, force majeure defense) with `document_count = 1` and a citation to
`northwind-v-contoso.md`.

---

## Part 2 — Test the interactive Teams bot (M365 Agents Playground)

The `frontend/teams-bot` (TypeScript) is the **interactive chat** component. It routes Teams
messages to the deployed `/api/chat/query` and renders **Adaptive Cards** with answer + citations.
You can test it **without a Teams tenant** using the **Microsoft 365 Agents Playground**.

> The Python `teams-messaging-app` is a separate **proactive broadcast** component — not used for
> interactive chat.

### 2.1 Prerequisites

- **Node.js** installed (this guide used v24).
- The bot's local config already points at the deployed API:
  - `frontend/teams-bot/.localConfigs` →
    `AGENT_URL=https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io`
  - SSO values (clientId/clientSecret/tenantId) are intentionally **blank** for Playground use.
    Free-form chat works; the `show` profile command (which needs SSO) does not.
- `node_modules` present in `frontend/teams-bot` (run `npm install` there if missing).

### 2.2 Step 1 — Install the M365 Agents Playground (one time)

VS Code task: **Teams Bot: Install M365 Agents Playground**, or run:

```powershell
winget install --id Microsoft.M365AgentsPlayground -e `
  --accept-source-agreements --accept-package-agreements
```

This installs the `agentsplayground` CLI and adds it to PATH.

> After install, **open a new terminal** so the updated PATH is picked up. If `agentsplayground`
> isn't recognized in an existing shell, call it by full path:
> `& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Microsoft.M365AgentsPlayground_Microsoft.Winget.Source_8wekyb3d8bbwe\agentsplayground.exe"`

### 2.3 Step 2 — Start the bot dev server

VS Code task: **Teams Bot: Start Dev (Playground)**, or run:

```powershell
cd frontend/teams-bot
npm run dev:teamsfx
```

This runs `env-cmd -f .localConfigs npm run dev` (nodemon + ts-node). Wait for:

```
Server listening to port 3978 on sdk 1.4.2 ...
```

The bot listens on `http://localhost:3978/api/messages`. Leave this terminal running.

### 2.4 Step 3 — Launch the Playground UI

VS Code task: **Teams Bot: Launch Playground UI**, or run (in a **new** terminal):

```powershell
agentsplayground -e http://localhost:3978/api/messages -c msteams
```

The CLI prints something like `Microsoft 365 Agents Playground ... http://localhost:56150` and
logs `Connected.` once it reaches the bot.

### 2.5 Step 4 — Chat and verify

1. Open the Playground URL (e.g. `http://localhost:56150`) in a browser.
2. In **Personal Chat**, the bot sends a welcome card.
3. Type a question, e.g. **`What is the dispute in case CW-2024-0182?`**, and press Send.
4. The bot shows a typing indicator while the agentic retrieval runs (a few seconds), then
   renders a **Casewright Adaptive Card** with the grounded answer and a **Sources** section,
   e.g. `[1] northwind-v-contoso.md`.

Other things to try:

- Multi-turn follow-ups — the bot derives a **stable UUID session_id per conversation**, so
  context is preserved across turns.
- `sites` — scope subsequent questions to a specific SharePoint site.

### 2.6 Notes & limitations

- The `show` profile command will not work in the Playground because SSO is intentionally
  unconfigured in `.localConfigs`. Free-form Q&A still routes to the backend.
- Playground does not process the app manifest; tabs/meeting extensions and some Adaptive Card
  features are unsupported (these don't affect the chat demo).

---

## Appendix — End-to-end flow

```
Playground UI  ->  local bot (localhost:3978)  ->  deployed casewright-api
   ->  POST /api/chat/query  ->  agentic RAG (Cosmos DB + Azure AI Search)
   ->  grounded answer + citations  ->  Adaptive Card in chat
```

## Appendix — Troubleshooting (deployed backend)

If a query returns an error after a redeploy or over time, two Azure settings are known to drift
to `Disabled` (security baseline audit policies flag them):

- **`/api/chat/query` returns 500 `(Forbidden) ... blocked by Cosmos DB firewall`** — re-enable
  public network access on Cosmos:

  ```powershell
  az cosmosdb update -g rg-casewright-dev -n casewright-cosmos-wrlidt67 --public-network-access Enabled
  ```

- **Scheduler deploy fails 403 (`InaccessibleStorageException`/`BlobUploadFailedException`)** —
  re-enable public access on the function storage account, then wait a few minutes and redeploy:

  ```powershell
  az storage account update -g rg-casewright-dev -n casewrightfnwrlidt67 --public-network-access Enabled
  ```
