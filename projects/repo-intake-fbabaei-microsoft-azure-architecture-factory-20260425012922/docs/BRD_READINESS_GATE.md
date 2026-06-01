# BRD Readiness Gate

Use this gate before treating a BRD as a candidate for fully automated execution through Azure Architecture Factory.

If you need a fill-in worksheet, use [BRD_READINESS_SCORECARD.md](BRD_READINESS_SCORECARD.md).

## Outcome Classes

### 1. Auto-Ready

Use this class when the BRD is specific enough that the factory can generate a credible Azure project baseline with minimal human correction.

Required signals:

- Clear business objective and named user or system actors
- Azure-first or Azure-compatible hosting assumptions
- Explicit workload type such as web app, API, microservices, workflow, AKS platform, or internal line-of-business app
- Named functional capabilities and main domain entities
- Minimum non-functional requirements for security, availability, observability, and deployment environment
- No major unknowns about identity, data residency, or integration ownership

Typical examples:

- Internal self-service portal on Azure
- Containerized API platform with async messaging
- Standard CRUD application with Azure data services
- Azure-hosted AI-assisted application with known service boundaries

### 2. Auto-Ready With Guardrails

Use this class when the factory can still generate the initial project, but an architect should review key decisions before the output is treated as production-ready.

Typical triggers:

- Some non-functional requirements are incomplete or vague
- Several external integrations are mentioned but not owned or specified
- Data classification is implied but not explicitly documented
- Multiple Azure service options are possible and the BRD does not narrow them down
- The BRD mixes product goals with partial implementation constraints

Expected action:

- Run the factory to produce the baseline
- Require architecture review before infrastructure approval or deployment

### 3. Architect Review Required

Use this class when the BRD is too ambiguous, too cross-domain, or too constrained for safe automated generation without prior architectural clarification.

Typical triggers:

- The BRD is not Azure-first and assumes other clouds, legacy platforms, or vendor-specific runtimes
- Critical compliance constraints are missing or contradictory
- Identity model, network boundaries, or deployment ownership are undefined
- The workload is heavily data-platform-specific, highly regulated, or modernization-heavy
- The BRD is mostly business language with little operational or technical context
- The requested system combines unrelated workload types without clear boundaries

Expected action:

- Do not treat the output as auto-ready
- Run architecture review first
- Convert the BRD into a clarified implementation brief before orchestration

## Checklist

Score each item as:

- `Pass`
- `Partial`
- `Fail`

### Scope And Business Intent

- Primary business outcome is explicit
- Main users, systems, or personas are identified
- Core capabilities are listed in a bounded way
- Success criteria are stated

### Workload Shape

- Target workload type is recognizable
- Expected interaction model is clear: synchronous API, event-driven, batch, portal, agentic app, or platform workload
- Major service boundaries or domains can be inferred
- The BRD does not collapse unrelated systems into one vague deliverable

### Azure Fit

- Azure is explicitly required or clearly acceptable
- Hosting model can be mapped to Azure services
- Required integrations are Azure-compatible
- No hard dependency contradicts the repo's Azure-first design

### Data And Integration Clarity

- Main data entities or documents are named
- Data sources and sinks are identified
- External systems and integration patterns are described
- Data sensitivity or classification is mentioned

### Non-Functional Requirements

- Security expectations are stated
- Availability or resiliency expectations are stated
- Monitoring or operational visibility is expected
- Environment expectations such as dev, test, and prod are stated

### Delivery Readiness

- The BRD is detailed enough to create a diagram
- The BRD is detailed enough to scaffold source structure
- The BRD is detailed enough to generate infrastructure assumptions
- The BRD is detailed enough to produce testable acceptance paths

## Classification Rule

Use this simple rule:

- `Auto-Ready`: no `Fail` in Azure Fit or Non-Functional Requirements, and at least 80% of all checks are `Pass`
- `Auto-Ready With Guardrails`: no more than 2 `Fail` overall, and none of them are in Azure Fit
- `Architect Review Required`: any `Fail` in Azure Fit, or more than 2 `Fail` overall, or missing identity/network/compliance context

## Minimum BRD Fields For Reliable Factory Output

These fields are the practical minimum for good results:

- Problem statement
- Users or system actors
- Functional requirements
- Data inputs and outputs
- External integrations
- Security expectations
- Availability expectations
- Deployment environment or hosting intent

## Recommended Operating Pattern

1. Run this gate on every incoming BRD.
2. Fill out [BRD_READINESS_SCORECARD.md](BRD_READINESS_SCORECARD.md) when a documented assessment is needed.
3. Mark the BRD as `Auto-Ready`, `Auto-Ready With Guardrails`, or `Architect Review Required`.
4. Only send `Auto-Ready` BRDs directly into `project-orchestrator` without pre-review.
5. For `Auto-Ready With Guardrails`, generate the baseline but hold deployment until architecture review is complete.
6. For `Architect Review Required`, refine the BRD before using the factory as the implementation engine.

## Current Honest Positioning For This Repository

Based on the current sample portfolio and validation evidence, Azure Architecture Factory should be treated as:

- Strong for many Azure application BRDs
- Reasonable for guided baseline generation across several workload types
- Not yet safe to market internally as universally ready for any BRD without a gate like this one
