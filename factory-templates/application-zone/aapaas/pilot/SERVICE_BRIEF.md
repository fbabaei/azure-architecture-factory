# AAPAAS service brief

## What AAPAAS is

AAPAAS, AI Apps as a Service, is a repeatable service for delivering secure, governed, production-ready AI applications through a factory, app-pack catalog, deployment workflow, and day-2 operating model.

## What users get

- A guided intake and readiness review.
- A choice between a certified app pack or a custom AI app build.
- Secure-by-default Azure deployment.
- App-pack certification checks.
- Health, operational, and evaluation evidence.
- Day-2 support patterns for monitoring, upgrades, rollback, and improvement.

## Initial app-pack catalog

| Pack | Purpose | Status |
| --- | --- | --- |
| CaseWright | Knowledge assistant over case/policy content using RAG, Azure AI Search, Foundry, and SharePoint ingestion | Healthy API/worker reference instance |
| Compliance Agent | Compliance copilot with RAG, document extraction, HITL approval, and audit history | Candidate |
| Supply Chain Control Tower | Multi-agent planning assistant for demand, supply, inventory, supplier risk, and human-approved replenishment | Candidate |
| Mailer Automation | OCR/vision/RAG/human-review workflow for mail processing | Candidate |

## MVP proof point

CaseWright is the first AAPAAS reference app pack. The current dev instance has:

- API and worker deployed to Azure Container Apps.
- Health endpoint passing.
- Azure AI Search in East US.
- Core runtime in East US 2.
- Scheduler Function App provisioned but package deployment pending.

## Success criteria

- Deploy or register one app-pack instance.
- Show health and deployment evidence.
- Show catalog and manifest-driven configuration.
- Show security and operations gates.
- Show how another candidate pack would be promoted.
