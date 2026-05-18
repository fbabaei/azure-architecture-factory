# MDR Support - BRD Gap Analysis

- Project: `mdr-support-20260416174652`
- Analysis date: 2026-04-17
- Analyst model: Crest Alpha V2 (Preview)
- Scope: Source code and architecture reevaluation against the MDR support BRD
- Mode: Read-only review; no source or architecture files were changed during the reevaluation

## Overall Assessment

The MDR support project is aligned with the BRD as a Phase 1 foundation. It supports MDR-specific Q&A, document upload and extraction, human-in-the-loop clarification, structured JSON draft generation, Azure-oriented architecture, and repeatable local tests.

The project is not yet production-ready. The remaining gaps are concentrated in deployment completeness, runtime security, managed identity role wiring, observability, resilience, upload hardening, and compliance auditability.

## BRD Capabilities Present

- MDR-specific Q&A is implemented through the `/qa` endpoint and Q&A service.
- Document upload and extraction are implemented through the arrangement upload flow, Blob Storage integration, and Document Intelligence integration path.
- Human-in-the-loop clarification is implemented through chat-session state management and missing-field detection.
- Structured MDR JSON draft generation is implemented through the MDR arrangement model and draft endpoint.
- Batch processing is explicitly deferred, which matches the Phase 1 BRD scope.
- Azure architecture is broadly appropriate: Container Apps, API Management, Azure OpenAI, Document Intelligence, Blob Storage, Cosmos DB, managed identity, Key Vault, Application Insights, and Log Analytics.

## Critical Gaps

### 1. No Dockerfile

Evidence: The project targets Azure Container Apps and deployment docs reference image build steps, but the project has no Dockerfile.

Why it matters: The app cannot be packaged and deployed cleanly. Without an application image, the Container Apps deployment path is incomplete.

Improvement suggestion: Add a Python 3.11 slim Dockerfile with a uvicorn entrypoint for `mdr_agent.main:app`, plus a `.dockerignore` file.

### 2. No RBAC Role Assignments in Bicep

Evidence: `infra/main.bicep` creates a managed identity and disables local authentication for key Azure services, but does not define role-assignment resources.

Why it matters: Azure OpenAI, Document Intelligence, Blob Storage, Cosmos DB, and Key Vault calls can fail at runtime unless roles are manually assigned after deployment.

Improvement suggestion: Add Bicep role assignments for Azure OpenAI User, Cognitive Services User, Storage Blob Data Contributor, Cosmos DB data access, Key Vault Secrets User, and monitoring roles.

### 3. Observability Is Provisioned but Not Initialized

Evidence: Infrastructure provisions Application Insights and Log Analytics, and the project includes `azure-monitor-opentelemetry`, but the FastAPI application does not initialize telemetry.

Why it matters: Production requests, dependency calls, exceptions, traces, and latency data will not be captured despite the Azure resources existing.

Improvement suggestion: Initialize Azure Monitor/OpenTelemetry during FastAPI startup when `APPLICATIONINSIGHTS_CONNECTION_STRING` is available.

### 4. API Security Is Not Enforced End-to-End

Evidence: API Management exists in infrastructure, but no APIM API or JWT validation policy is configured. The Container App ingress remains publicly reachable, and FastAPI has no bearer-token validation.

Why it matters: Sensitive MDR arrangement data could be exposed through the public Container App endpoint.

Improvement suggestion: Add APIM API resources and a `validate-jwt` policy, restrict direct backend access, and optionally add app-level bearer-token validation as defense in depth.

## High-Priority Gaps

### 5. No Retry or Backoff Around Azure Calls

Evidence: Azure OpenAI, Document Intelligence, and Cosmos calls do not have an explicit transient-fault strategy.

Why it matters: Throttling and temporary network failures are normal in cloud services. Without retry logic, users see avoidable failures.

Improvement suggestion: Add bounded exponential backoff around Azure SDK calls, especially OpenAI completion calls, Document Intelligence analysis calls, and Cosmos persistence operations.

### 6. Clarification Answer Parsing Is Still Heuristic

Evidence: Complex fields such as parties and hallmarks are still populated with simple parsing logic in the chat-session flow.

Why it matters: Users can provide rich MDR answers that get flattened, misclassified, or accepted with weak validation.

Improvement suggestion: Use focused structured-extraction prompts for complex clarification answers, with current heuristic parsing retained as a fallback.

### 7. Upload Validation Is Too Weak

Evidence: The upload endpoint reads the full file into memory and does not strongly enforce size or content-type constraints.

Why it matters: Large or invalid uploads can cause memory pressure, wasted Document Intelligence cost, or denial-of-service risk.

Improvement suggestion: Enforce file size limits, allowed content types, empty-file checks, and safer streaming behavior.

### 8. No Compliance Audit Trail

Evidence: Chat turns are persisted, but there is no dedicated audit record for user identity, upload, extraction, clarification, or draft finalization.

Why it matters: MDR/DAC6 workflows require traceability of who performed which action and when.

Improvement suggestion: Add an audit container or structured audit events with user identity, arrangement ID, action, timestamp, and outcome.

## Medium and Low-Priority Improvements

- Key Vault is deployed but not meaningfully used. Either wire real secrets through it or remove it for Phase 1.
- Tests cover core happy paths but need more failure-mode coverage.
- Jurisdiction fallback extraction should validate against ISO country codes rather than broad uppercase-token matching.
- Add a `/ready` endpoint separate from `/health` to validate dependency readiness.
- Add OpenAPI tags and examples for easier portal and API consumption.
- Add tests for malformed LLM JSON, Azure throttling, oversized uploads, invalid hallmarks, invalid jurisdictions, and concurrent chat turns.

## Recommended Implementation Order

1. Add Dockerfile and `.dockerignore`.
2. Add RBAC role assignments in Bicep.
3. Initialize Azure Monitor/OpenTelemetry.
4. Enforce APIM/JWT security and restrict direct backend access.
5. Add retry/backoff for Azure calls.
6. Add upload validation.
7. Improve structured parsing for clarification answers.
8. Add audit logging.
9. Expand failure-path test coverage.
10. Clean up or activate Key Vault usage.

## Bottom Line

The project is good as a local Phase 1 proof of concept and matches the BRD's intended workflow. The critical blockers must be closed before it is a defensible Azure pilot.
