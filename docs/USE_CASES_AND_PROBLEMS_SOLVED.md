# Use Cases And Problems Solved

## Azure Architecture Factory

This document summarizes the main internal scenarios the repository supports.

## 1. Requirements To Project Baseline

**Problem:** Teams receive a BRD or PRD and need a credible Azure project baseline quickly.

**Factory response:** Use `project-orchestrator` to create an isolated project folder with diagrams, source structure, infrastructure, logs, and supporting docs.

## 2. Diagram-First Architecture Delivery

**Problem:** Teams want architecture artifacts to stay connected to implementation instead of becoming stale side documents.

**Factory response:** Treat `diagrams/` as source artifacts and use `brd-to-architecture-diagram` plus `azure-architecture-implementer` as the main flow.

## 3. Infrastructure Validation Before Deployment

**Problem:** Bicep issues are often discovered too late.

**Factory response:** Use `bicep-infrastructure-validator` before deployment and expose validation behavior through the project workflow.

## 4. Production Readiness Review

**Problem:** Security, identity, networking, and monitoring prerequisites are often handled late.

**Factory response:** Use `production-environment-advisor` to create explicit readiness checklists and blockers.

## 5. Sample Portfolio Review

**Problem:** Stakeholders need evidence that the repo creates real project artifacts, not only diagrams or templates.

**Factory response:** Use the sample-project portfolio in `projects/` and the readiness dashboard in `demo/` to review the current evidence.

## 6. Current Strongest Example

`order-management-platform` is the strongest current proof point because it includes:

- Architecture diagram and notes
- Source code structure
- Tests
- Infrastructure
- Production checklist
- Deployment guide
- Manifest-based readiness data

## 7. Legacy Application Modernization to Azure Baseline

**Problem:** Teams have an existing application (monolith, legacy service, or AWS function) that needs to be re-platformed onto Azure. The pain is that modernization assessment tools produce findings but not an Azure project ready to build — there is a gap between "what is wrong" and "what to build."

**Factory response:** Use `modernization-to-factory` to bridge that gap. The agent:
1. Inspects the legacy codebase — technology stack, architecture pattern, modernization debt, and migration risks.
2. Maps each legacy component to its Azure target service.
3. Writes a `modernization-assessment.md` with full assessment evidence.
4. Generates a structured target-state BRD (`requirements.md`) from the assessment.
5. Hands the BRD to `project-orchestrator`, which runs the full factory pipeline: architecture diagram, implementation scaffolding, Bicep infrastructure, production readiness review, and optional deployment.

**Seam with external assessment tools:** If a `modernize-java`, `modernize-dotnet`, or `azure-cloud-migrate` agent has already produced findings, those findings can be summarized into the BRD input before invoking `project-orchestrator` directly — skipping `modernization-to-factory` Phase 1 and Phase 2.

Example invocation:
```
modernization-to-factory:
  legacy-path: legacy-app/
  technology: java
  project-name: modernized-order-service
  azure-region: eastus
```

## 8. Current Gap Pattern

Not every sample project is equally complete. Some projects emphasize infrastructure or UX more than tests and deployment guidance. That is acceptable for internal evaluation as long as the portal reports those differences honestly.
