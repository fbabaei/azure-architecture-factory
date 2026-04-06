# Product Requirements Document

## Azure Architecture Factory

**Version:** 2.1  
**Date:** April 2026

## 1. Product Summary

Azure Architecture Factory is an internal platform that uses custom Copilot agents to convert requirements into Azure project outputs. The target outputs are not limited to diagrams or infrastructure; the platform aims to create project folders that include architecture artifacts, source code, tests, documentation, and deployment guidance.

## 2. Product Goal

Reduce the time and inconsistency between receiving a requirement and producing a credible Azure project baseline.

## 3. Core Capabilities

| Capability | Description |
| --- | --- |
| Requirements intake | Accept BRD, PRD, or structured prompt input |
| Architecture generation | Produce or import Azure Draw.io diagrams and notes |
| Implementation scaffolding | Create service-oriented source structure and supporting docs |
| Infrastructure generation | Produce Bicep modules and parameter files |
| Validation | Detect and fix Bicep issues before deployment |
| Production review | Generate readiness prerequisites and blockers |
| Deployment | Optionally deploy prepared projects to Azure |
| Evidence reporting | Surface repository readiness through the developer portal |

## 4. Intended Output Structure

Each generated project should converge on the following shape:

```text
projects/<slug>/
├── docs/
├── diagrams/
├── src/
├── infra/
├── tests/
├── logs/
├── project-manifest.json
├── README.md
└── DEPLOY.md
```

## 5. Product Constraints

- The platform must keep each generated project isolated.
- The platform must preserve diagram-driven architecture flow rather than bypassing architecture artifacts.
- Deployment must remain optional and explicit.
- Validation must happen before deployment.
- Repo-level messaging should stay general-purpose and not depend on one showcase workload.

## 6. Current Repository Evidence

The repository currently shows different maturity levels across sample outputs:

| Project | Architecture | Source | Docs | Tests | Infra | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `order-management-platform` | Yes | Yes | Yes | Yes | Yes | Strongest full-lifecycle example |
| `storage-self-service-provisioning` | Yes | Yes | Yes | Yes | Partial | Good service workflow example |
| `aks-microservices-demo` | Partial | Yes | Yes | Limited | Yes | Platform and AKS emphasis |
| `ecommerce-demo` | Limited | Partial | Partial | No | No | Lightweight demo output |

## 7. Product Success Criteria

| Measure | Target |
| --- | --- |
| A sample project can show diagram + source + docs + tests | Yes |
| At least one sample demonstrates production-style completeness | Yes |
| Validation can be run from the developer portal | Yes |
| Shared docs describe the repo as a factory, not a single-project template | Yes |
| Multiple workload types can be represented | Yes |

## 8. Non-Goals

- Replace all engineering customization after generation.
- Guarantee that every sample project is production-ready without project-specific follow-up.
- Act as a generic website showcase with no connection to real repository artifacts.

## 9. Immediate Product Priorities

1. Strengthen consistency across sample projects so more than one project meets full-lifecycle completeness.
2. Keep the developer portal tied to actual repository evidence.
3. Expand test coverage and manifest quality across lighter-weight samples.
4. Maintain diagram-first delivery as the primary operating model.
