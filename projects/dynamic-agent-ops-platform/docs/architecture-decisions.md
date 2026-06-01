# Architecture Decisions — Dynamic Agent Orchestration Platform (DAOP)

## AD-001: MAF SDK as Primary Agent Runtime
**Decision:** All agent logic uses the Microsoft Agent Framework (MAF) SDK, not raw OpenAI API.  
**Rationale:** MAF provides managed thread state, built-in tool-calling, and Foundry integration out of the box. Raw OpenAI API would require re-implementing thread management and tool dispatch.  
**Consequence:** Projects must run `scripts/install_agent_framework.sh` or `.ps1` before `azd up`.

## AD-002: Deterministic Fallback Runtime
**Decision:** Every agent service ships both an SDK runtime and a deterministic Python fallback.  
**Rationale:** Ensures the service stays online if Foundry is unreachable or the SDK is not installed (local dev, CI).  
**Consequence:** Each service maintains two code paths; the factory pattern in `config.py` switches between them.

## AD-003: Cosmos DB for Agent Registry and Session State
**Decision:** Azure Cosmos DB (NoSQL API) stores agent templates, active sessions, and shared project context.  
**Rationale:** Cosmos DB provides low-latency reads, flexible schema for evolving template definitions, and multi-region replication for production.  
**Consequence:** Local development requires a Cosmos DB emulator or a dev-tier account.

## AD-004: Service Bus for Async Task Decoupling
**Decision:** Long-running agent tasks are dispatched via Azure Service Bus queues.  
**Rationale:** Agent tasks (code generation, IaC scaffolding, security scans) can exceed HTTP timeout windows. Service Bus enables fire-and-poll / callback patterns.  
**Consequence:** The orchestrator must implement a polling or callback mechanism for task results.

## AD-005: AAF as External Tool Only
**Decision:** AAF is consumed exclusively via its HTTP API; no shared code or packages.  
**Rationale:** Maintains platform independence; AAF is treated as a stable external service with a versioned API contract.  
**Consequence:** The AAF tool adapter must handle AAF API versioning and error responses gracefully.

## AD-006: User-Assigned Managed Identity
**Decision:** A single user-assigned managed identity (`daop-identity`) is shared across all Container Apps.  
**Rationale:** Simplifies RBAC management; all services have identical access to Key Vault, Cosmos DB, and Foundry.  
**Consequence:** All services use `DefaultAzureCredential` with no fallback to key-based auth in production.
