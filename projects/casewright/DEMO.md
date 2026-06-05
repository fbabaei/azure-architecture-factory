# Casewright Demo — Grounded RAG Chat Walkthrough

This walkthrough takes a brand-new user from zero to a **grounded chat answer with citations**
against the deployed Casewright stack. It uses only the deployed HTTP API plus Azure CLI for the
one-time document upload — no SharePoint/Graph credentials required.

## What you'll prove

By the end, `POST /api/chat/query` returns an answer with `document_count > 0` and `citations`,
grounded on a sample legal case document you ingest yourself.

## Environment (deployed dev stack)

| Thing | Value |
| --- | --- |
| API base URL | `https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io` |
| Subscription | `729fcdbd-c547-48df-a749-dbee6cdb50b0` |
| Resource group | `rg-casewright-dev` |
| Storage account | `casewrightstwrlidt67` |
| Ingestion container | `ingestion` |
| Search service | `casewright-search-wrlidt67` (westus3) |
| Search index | `casewright-index` |
| Sample document | `scripts/sample_docs/northwind-v-contoso.md` |

> The Search service has `disableLocalAuth = true`, so all data-plane access is **RBAC only**.
> You upload the document with your own Entra identity (Storage Blob Data Contributor), and the
> indexer reads it using the API's managed identity.

---

## Prerequisites

- Azure CLI 2.60+ (`az version`)
- Signed in: `az login`
- Storage Blob Data Contributor on the storage account (granted to the demo user)

---

## Step 1 — Sign in and select the subscription

```pwsh
az account set --subscription 729fcdbd-c547-48df-a749-dbee6cdb50b0
az account show --query "{name:name, user:user.name}" -o table
```

## Step 2 — Health check the API

Confirm the deployed API is up before doing anything else.

```pwsh
$base = "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io"
Invoke-RestMethod "$base/api/health" | ConvertTo-Json
```

Expected: `{ "status": "ok", "service": "casewright-api" }`.

## Step 3 — Baseline: ask before any documents exist

Show that the chat is honest about having nothing to ground on.

```pwsh
$base = "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io"
$body = @{
  query      = "What are the claims in the Northwind v. Contoso case?"
  session_id = [guid]::NewGuid().ToString()
  user_id    = "demo-user"
} | ConvertTo-Json
$r = Invoke-RestMethod -Method Post "$base/api/chat/query" -ContentType "application/json" -Body $body
"document_count = $($r.document_count); citations = $($r.citations.Count)"
$r.answer
```

If the index is already seeded from a prior run you may see citations here; that's fine.

## Step 4 — Upload the sample document to the ingestion container

The indexer ingests whatever lands in the `ingestion` blob container.

```pwsh
az storage blob upload `
  --account-name casewrightstwrlidt67 `
  --container-name ingestion `
  --name northwind-v-contoso.md `
  --file scripts/sample_docs/northwind-v-contoso.md `
  --auth-mode login `
  --overwrite
```

## Step 5 — Run the indexer

Trigger ingestion (chunk → embed → project into the index).

```pwsh
$base = "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io"
Invoke-RestMethod -Method Post "$base/api/pipeline/run-indexer" | ConvertTo-Json
```

## Step 6 — Wait for the indexer to finish

Poll until `status` reports success and `document_count` (indexed docs) is at least 1.

```pwsh
$base = "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io"
do {
  Start-Sleep -Seconds 10
  $s = Invoke-RestMethod "$base/api/pipeline/indexer-status"
  "status=$($s.status) lastResult=$($s.last_result_status) items=$($s.items_processed)"
} while ($s.last_result_status -notin @("success","transientFailure") -and $s.status -ne "error")
```

## Step 7 — Ask again: grounded answer with citations

```pwsh
$base = "https://casewright-api.redrock-25d28f69.eastus2.azurecontainerapps.io"
$body = @{
  query      = "What are the claims in the Northwind v. Contoso case?"
  session_id = [guid]::NewGuid().ToString()
  user_id    = "demo-user"
} | ConvertTo-Json
$r = Invoke-RestMethod -Method Post "$base/api/chat/query" -ContentType "application/json" -Body $body
"document_count = $($r.document_count); citations = $($r.citations.Count)"
$r.answer
$r.citations | ForEach-Object { " - $($_.document_title) ($($_.document_id))" }
```

Expected: `document_count >= 1`, one or more `citations`, and an answer that cites the breach of
contract, liquidated damages, and consequential damages claims with `[1]`-style markers.

---

## Troubleshooting

- **401/403 on upload** — you lack Storage Blob Data Contributor on `casewrightstwrlidt67`.
  Ask an owner to grant it, then retry Step 4.
- **`run-indexer` 400 "indexer is disabled"** — older builds created indexers disabled. The
  current build re-enables before running; redeploy `casewright-api` if you hit this.
- **Chat returns 0 documents after indexing** — confirm Step 6 reported `success`; the index
  key field `content_id` must be searchable + filterable (it is in the current schema).
