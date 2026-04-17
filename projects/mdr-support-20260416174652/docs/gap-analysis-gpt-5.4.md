# MDR Support - Gap Analysis

- Project: `mdr-support-20260416174652`
- Analysis date: 2026-04-17
- Analyst model: GPT-5.4 (GitHub Copilot)

## Summary

The project now matches the BRD at the solution-shape level: it supports MDR-specific Q&A, document upload and extraction, a human-in-the-loop clarification loop, structured JSON drafting, Azure-oriented architecture, and repeatable tests. The main remaining gaps are in production hardening, security enforcement, deployment packaging, observability, and stronger MDR-specific field parsing.

## Highest-priority gaps

1. Identity is designed but not fully enforced.
   The infrastructure assigns a managed identity and disables local auth on core Azure services, but there are no RBAC role-assignment resources in `infra/main.bicep`. This can cause runtime authorization failures after deployment.
   Suggested improvement: add Bicep role assignments for Azure OpenAI, Document Intelligence, Blob Storage, Cosmos DB, Key Vault, and monitoring.

2. API security is not closed end-to-end.
   The architecture implies APIM and Entra ID protection, but the current deployment leaves the Container App externally reachable and there are no APIM API or JWT validation policies defined.
   Suggested improvement: add APIM API resources and `validate-jwt` policies, restrict direct backend access, and optionally validate bearer tokens in the FastAPI app as defense in depth.

3. Deployment artifact is missing.
   The project targets Azure Container Apps, but there is no Dockerfile for the application image. The deployment path is therefore incomplete.
   Suggested improvement: add a Dockerfile and `.dockerignore`, then wire image build and publish steps into the deployment flow.

4. Observability is provisioned but not initialized in code.
   Application Insights and Log Analytics are provisioned and the connection string is injected, but the application does not initialize Azure Monitor / OpenTelemetry.
   Suggested improvement: configure telemetry during FastAPI startup using `azure-monitor-opentelemetry` so requests, dependencies, failures, and traces are captured.

## Medium-priority gaps

5. Chat-driven field completion is still simplistic.
   The clarification flow works, but complex fields such as parties and hallmarks are still populated with basic heuristics.
   Suggested improvement: use a focused extraction prompt per answered field to convert free text into typed MDR structures.

6. Upload handling is not hardened.
   The API reads the full file into memory, which is not safe for larger real-world PDFs.
   Suggested improvement: enforce upload-size limits, validate content type, and stream or chunk uploads.

7. Azure SDK calls have no retry strategy.
   Transient throttling or network faults can surface directly as user-facing failures.
   Suggested improvement: add bounded retry and exponential backoff around Azure OpenAI and Document Intelligence calls.

8. Auditability is weak for a compliance workload.
   The app stores drafts and chat turns, but it does not maintain a clear audit trail of who performed which action and when.
   Suggested improvement: add structured audit events for upload, extraction, clarification, and draft finalization.

9. Key Vault is deployed but not meaningfully used.
   The architecture includes Key Vault, but the application does not currently consume any secrets from it.
   Suggested improvement: either wire real secrets through Key Vault-backed references or remove it until needed.

## Low-priority improvements

10. Tests focus on happy paths more than resilience.
    Suggested improvement: add failure-path tests for malformed LLM output, Azure dependency failures, Cosmos conflicts, and oversized uploads.

11. Heuristic extraction can misclassify jurisdictions.
    Suggested improvement: validate jurisdiction codes against a real ISO country-code list instead of broad uppercase-token matching.

12. Readiness checks are shallow.
    Suggested improvement: add a `/ready` endpoint that verifies critical downstream dependencies when Azure-backed mode is enabled.

## Recommended implementation order

1. Add Dockerfile and deployment packaging.
2. Add RBAC role assignments in Bicep.
3. Initialize Azure Monitor / OpenTelemetry in the app.
4. Enforce APIM and JWT-based authentication.
5. Harden uploads and add retry logic.
6. Improve structured parsing of clarification answers.
7. Add audit logging.
