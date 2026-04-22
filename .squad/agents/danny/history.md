# Danny — History

## Core Context

- **Project:** End-to-end pipeline that reads BRD/PRD documents, generates Azure architecture with code scaffolding, runs tests, and deploys to Azure upon approval.
- **Role:** Lead
- **Joined:** 2026-04-16T21:52:52.593Z

## Learnings

<!-- Append learnings below -->
- 2026-04-17: MDR support rerun shows the local Phase 1 app path is healthy, but production architecture claims must separate provisioned resources from enforced controls; APIM policies, RBAC, container buildability, key handling, and audit writes are the main readiness gaps.
- 2026-04-17: For MDR rerun reports, keep the filename/model slug stable and refresh validation tables with the latest repository-root pytest and health evidence before changing architectural conclusions.

## Learnings

- 2026-04-17 (Opus 4.7 rerun, mdr-support-20260416174652): Project delivers the shape of the compliance-agent reference design but diverges on the substrate — no Microsoft Agent Framework (two services, not two agents), gpt-4o instead of gpt-5.2, and no embeddings/vector path so 'hybrid RAG' is keyword-semantic only. Bicep provisions case-drafts and audit-log Cosmos containers that the application never writes; AI Search admin key is injected via env var contradicting the managed-identity posture; no project-local Dockerfile despite Container Apps deployment guidance. HITL loop is a deterministic MANDATORY_FIELDS state machine with lossy comma-split parsing (parties hardcoded to relevant_taxpayer, jurisdiction/TIN discarded) — functional for tests, below the stated LLM-driven design.

