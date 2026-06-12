# Azure Architecture Factory (AAF) Workflow Guide

This guide covers orchestration patterns, agent roles, quality gates, and production readiness workflows for projects driven by the Azure Architecture Factory.

---

## 1. Project Lifecycle Overview

### Three Main Pathways

| Pathway | Use Case | Start Point | Key Agents |
|---------|----------|-------------|-----------|
| **Greenfield** | New Azure application from scratch | BRD/PRD | `project-orchestrator` → architecture → code scaffold → deploy |
| **Modernization** | Upgrade/migrate legacy application to Azure | Existing codebase | `modernization-to-factory` → assessment → plan → execute |
| **Enhancement** | Add features to existing factory project | BRD update | Update BRD → `project-orchestrator` with `update: true` → targeted implementation |

---

## 2. BRD-Driven Development Workflow

### 2.1 Requirements Capture

1. **Write or Update BRD**
   - Location: `docs/BRD.md` or inline via chat prompt
   - Sections: user stories, functional/non-functional requirements, Azure service preferences, compliance/SLA needs
   - See: [docs/BRD.md](BRD.md) for template and examples

2. **Validate BRD Readiness**
   - Check BRD completeness using clarity criteria from `docs/BRD_READINESS_GATE.md`
   - Ensure all services, dependencies, deployment targets are defined
   - Confirm team understands acceptance criteria

### 2.2 Architecture Generation

3. **Invoke project-orchestrator**
   ```
   Use: project-orchestrator
   Input: BRD.md (or inline requirements)
   Output: 
     - Architecture diagram (draw.io)
     - Companion notes
     - Project folder structure
     - Implementation plan
   ```

4. **Review Architecture Diagram**
   - Located in `projects/<slug>/diagrams/`
   - Validates service components, data flows, Azure resources
   - Compare against BRD requirements — ensure 1:1 mapping
   - Saved as source of truth for implementation

### 2.3 Implementation & Code Sync

5. **Implementation Phase**
   - `project-orchestrator` scaffolds:
     - Source code under `projects/<slug>/src/`
     - Infrastructure (Bicep or Terraform) under `projects/<slug>/infra/`
     - Service-to-service contracts
   
6. **Keep Code in Sync with Architecture**
   - Use `source-code-maintainer` when architecture changes:
     - Detects drift between diagram and code
     - Updates service contracts and adapters
     - Regenerates tests and docs
   - Mode options: `sync`, `drift-check`, `add-to-service`, `refactor`

---

## 3. Agent Roles and Responsibilities

### Core Orchestration

| Agent | Responsibility | When Used |
|-------|-----------------|-----------|
| **project-orchestrator** | End-to-end project lifecycle: BRD → architecture → code → infra → deploy | Greenfield or major updates |
| **brd-to-architecture-diagram** | Generate architecture diagram from BRD | Before project-orchestrator or when updating architecture |
| **drawio-architecture-reader** | Analyze and validate architecture diagrams | During architecture review phase |

### Implementation & Code

| Agent | Responsibility | When Used |
|-------|-----------------|-----------|
| **source-code-maintainer** | Scaffold, sync, and maintain application source code | After orchestrator or on architecture changes |
| **lang-dotnet-implementer** | Generate ASP.NET Core services (.NET 8 LTS) | Dotnet projects |
| **azure-architecture-implementer** | Read diagrams, map to Azure resources, scaffold microservices | Complex multi-service architectures |

### Infrastructure & Deployment

| Agent | Responsibility | When Used |
|-------|-----------------|-----------|
| **azure-project-deployer** | Deploy Bicep/Terraform and application services to Azure | After infra validation (Phase 4) |
| **bicep-infrastructure-validator** | Validate and auto-fix Bicep modules and parameters | Before deploy, on IaC changes |
| **terraform-infrastructure-validator** | Validate and auto-fix Terraform configs | Terraform-based projects before deploy |
| **aca-express-deployer** | Deploy HTTP workloads to Azure Container Apps Express | Fast, sub-minute container deployments |

### Governance & Quality Gates

| Agent | Responsibility | When Used |
|-------|-----------------|-----------|
| **contract-validator** | Validate inter-agent handoffs (intake/design/architecture/agent-tooling contracts) | At phase boundaries |
| **security-compliance-auditor** | Audit services, Bicep, dependencies for security/compliance gaps | Phase 2.6 (before production readiness) |
| **project-cost-analyzer** | Analyze actual and projected Azure costs | Post-deployment cost review |
| **project-observability-advisor** | Audit monitoring, logging, distributed tracing setup | Production readiness sign-off |
| **project-traceability-advisor** | Map requirements to code, tests, Bicep; compute coverage | Final validation before release |

### Modernization & Migration

| Agent | Responsibility | When Used |
|-------|-----------------|-----------|
| **modernization-to-factory** | Assess legacy codebase and generate Azure target baseline | Starting modernization workflow |
| **modernize** | Coordinate assess → plan → execute for upgrades and migrations | Java/dotnet upgrades, cloud migrations |

---

## 4. Project Orchestrator Workflow (Phases 1–5)

### Phase 1: Intake & Validation
- Input: BRD.md or inline requirements
- Output: project-manifest.json, initial folder structure
- Validation: BRD completeness, naming conventions

### Phase 2: Design & Architecture
- **2.1–2.5**: Architecture diagram generation, service design, infrastructure modules, dependency analysis
- **2.6**: Security & compliance audit (findings report)
- **2.7**: Cost estimation
- **2.8**: Scalability & resilience review

### Phase 3: Implementation
- Code scaffolding, test stubs, docstrings
- Service-to-service contracts
- Shared library generation

### Phase 4: Production Readiness Review
- Infra validation (Bicep or Terraform)
- RBAC and managed identity validation
- Observability stack verification
- **4.5 Approval Gate**: Manual sign-off is required before deployment (use `approval_gate: false` only for non-production experiments with explicit risk acceptance documented in the project records)

### Phase 5: Deployment & Observability
- `azd deploy` or `terraform apply`
- Observability configuration
- Post-deployment smoke tests
- Cost and compliance baseline established

---

## 5. Quality Gates & Validation Checkpoints

### Pre-Architecture (Gate 1)
**BRD Readiness Scorecard** — See [docs/BRD_READINESS_GATE.md](BRD_READINESS_GATE.md)
- [ ] All requirements documented with acceptance criteria
- [ ] Azure services and regions specified
- [ ] Compliance/SLA/cost constraints defined
- [ ] Team consensus on approach

### Post-Architecture (Gate 2)
**Diagram-to-Spec Coverage**
- [ ] Every BRD requirement maps to architecture component
- [ ] Data flows align with service boundaries
- [ ] External dependencies (APIs, databases) documented
- [ ] Deployment topology (dev/test/prod) clear

### Pre-Implementation (Gate 3)
**Implementation Plan Quality**
- [ ] Tasks derived from architecture
- [ ] Requirement traceability (REQ-IDs) established
- [ ] Test strategy aligned with architecture
- [ ] Delivery timeline and resource allocation clear

### Pre-Deployment (Gate 4)
**Production Readiness Checklist**
- [ ] Code review completed, tests passing
- [ ] Infra validation passed (no syntax/logic errors)
- [ ] Security audit findings remediated (or risk-accepted)
- [ ] Observability configured (Application Insights, Log Analytics, alerts)
- [ ] Cost estimate reviewed and within budget
- [ ] RBAC roles assigned with least-privilege
- [ ] Managed identities provisioned and scoped
- [ ] Secrets stored in Key Vault (none in source)
- [ ] Network security validated (NSGs, private endpoints, VNets)

### Post-Deployment (Gate 5)
**Operational Readiness Sign-Off**
- [ ] Application startup and health checks pass
- [ ] Telemetry flowing to Application Insights
- [ ] Alerts and runbooks in place
- [ ] Cost baseline established
- [ ] Compliance audit shows no critical findings
- [ ] Requirement coverage report generated and reviewed

---

## 6. Security & Compliance Review Process

### During Phase 2.6 Security Audit

1. **Invoke `security-compliance-auditor`**
   - Scans all services, Bicep modules, dependencies
   - Checks for: secrets, identity, authZ, network boundaries, CVEs, audit logging
   - Severity classification (critical/major/minor)

2. **Review Findings Report**
   - Located in `projects/<slug>/audit-findings.md`
   - Categorized by service and severity

3. **Remediation or Risk Acceptance**
   - For critical/major: require fixes before Gate 4
   - For minor: document risk acceptance in project-manifest.json
   - Update findings report with resolution status

---

## 7. Cost & Observability Reviews

### Pre-Deployment Cost Estimation

1. **Review Bicep/Terraform estimates**
   - Infrastructure costs included in project-orchestrator output
   - Cross-check against Azure pricing for region and SKU

2. **Adjust reserved capacity, autoscaling policies**
   - Update parameters in `infra/params/` (Bicep) or `terraform.tfvars.example` (TF)
   - Re-validate before approval

### Post-Deployment Cost Analysis

1. **Invoke `project-cost-analyzer`** (after 48–72 hours of traffic)
   - Compares actual spend vs. pre-deployment estimate
   - Identifies unused resources, rightsizing opportunities
   - Generates dated cost report in `projects/<slug>/reports/`

2. **Observability Audit**
   - Invoke `project-observability-advisor`
   - Verifies Application Insights, Log Analytics, distributed tracing
   - Recommends Bicep/Terraform fixes for missing configs

---

## 8. Requirement Traceability

### During Implementation

- Code uses structured comments: `// REQ-001: User authentication via Azure AD`
- Tests reference requirements: `test_user_can_login_via_azure_ad  # REQ-001`
- Bicep modules tagged with requirements: `// REQ-005: Multi-region failover setup`

### Pre-Release Sign-Off

1. **Invoke `project-traceability-advisor`**
   - Scans code, tests, Bicep for REQ-ID comments
   - Generates coverage metrics: implemented/tested/deployed percentages
   - Identifies unmapped requirements or orphaned code

2. **Review Traceability Report**
   - Ensure all BRD requirements traced to implementation
   - Validate no orphaned features in code
   - Sign-off on coverage before release

---

## 9. Modernization Workflow (Legacy Applications)

### Step 1: Assessment
```
Use: modernization-to-factory
Input: Existing codebase (Java, .NET, Python, Lambda, etc.)
Output: Structured BRD describing Azure target state
```

### Step 2: Planning
- Assess generates technology insights, cloud-readiness scores, risk factors
- Team reviews and agrees on target services (App Service, Container Apps, Functions, AKS)
- `modernization-to-factory` produces baseline BRD

### Step 3: Orchestration
- Pass generated BRD to `project-orchestrator`
- Generates target architecture, scaffolding, and Bicep/Terraform

### Step 4: Execution
- Use specialized agents:
  - **modernize-java** — Java version/Spring Boot upgrades
  - **modernize** — Cross-cloud migration (Lambda→Functions, etc.)
  - **modernize-rearchitecture** — Multi-agent team for rearchitecture tasks

### Step 5: Validation & Deployment
- Run integration tests (Layer 1–4 as per runtime-validation skill)
- Invoke `security-compliance-auditor` before going live
- Deploy using `azure-project-deployer`

---

## 10. Specialized Skills Reference

### When to Use Each Skill

| Skill | Trigger | Output |
|-------|---------|--------|
| **azure-prepare** | "create app", "deploy to Azure", "set up infrastructure" | Bicep/Terraform + azure.yaml + Dockerfiles |
| **azure-validate** | "check deployment readiness", "validate my app" | Deep preflight checks report |
| **azure-deploy** | "run azd up", "execute deployment", "push to Azure" | Deployed resources + logs |
| **azure-diagnostics** | "debug production issues", "troubleshoot app service" | Root cause analysis + remediation guidance |
| **azure-cost** | "query Azure costs", "forecast spending", "optimize costs" | Cost breakdown, rightsizing recommendations |
| **azure-compliance** | "compliance scan", "security audit", "BEFORE running azqr" | Compliance report + remediation steps |
| **azure-kubernetes** | "create AKS", "provision cluster", "secure AKS" | AKS architecture + Bicep scaffolding |
| **azure-rbac** | "what role should I assign", "least privilege access" | RBAC recommendations + CLI/Bicep commands |
| **azure-storage** | "blob storage", "file shares", "access tiers" | Storage architecture + tier comparison |

See [docs/Workflow Guide](WORKFLOW_GUIDE.md) for additional specialized skills.

---

## 11. Handling BRD Updates on Existing Projects

### When Requirements Change

1. **Update BRD.md** in project folder or root docs
2. **Invoke project-orchestrator with update flag**
   ```
   Use: project-orchestrator
   Input: 
     update: true
     slug: <existing-project-slug>
     (updated BRD content)
   Output: Diff of changes, updated architecture, targeted implementation updates
   ```
3. **Steps taken by orchestrator**:
   - Diffs new BRD against current architecture
   - Regenerates diagram with deltas highlighted
   - Applies targeted code/infra changes only (not full re-scaffold)
   - Updates traceability map with new REQ-IDs
4. **Team reviews** changed components and approves before merge

---

## 12. Production Readiness Checklist

### Before Phase 4.5 Approval Gate

- [ ] **Code Quality**
  - [ ] Peer review completed
  - [ ] Unit tests pass with >80% coverage
  - [ ] Integration tests passing
  - [ ] No lint errors or warnings

- [ ] **Infrastructure**
  - [ ] Bicep/Terraform syntax validated
  - [ ] Parameter files reviewed and secured
  - [ ] No hardcoded secrets or connection strings
  - [ ] Multi-region or HA configured (if required by SLA)

- [ ] **Security & Compliance**
  - [ ] Security audit completed; critical findings remediated
  - [ ] Managed identities configured with least-privilege RBAC
  - [ ] Key Vault provisioned; secrets rotated (if applicable)
  - [ ] Network security validated (NSGs, firewalls, private endpoints)
  - [ ] Audit logging enabled and flowing to Log Analytics

- [ ] **Observability**
  - [ ] Application Insights configured
  - [ ] Distributed tracing (W3C TraceContext) enabled
  - [ ] Alerts defined for business metrics and error rates
  - [ ] Runbooks documented for on-call response

- [ ] **Cost & Performance**
  - [ ] Cost estimate reviewed and approved
  - [ ] Performance baseline established (API latency, throughput)
  - [ ] Autoscaling policies defined and tested
  - [ ] Capacity reserved (if needed for SLA)

- [ ] **Documentation**
  - [ ] README.md explains architecture and setup
  - [ ] Runbooks provided for common operational tasks
  - [ ] Traceability report generated (all requirements mapped)
  - [ ] Change log updated with deployment details

---

## 13. Common Workflows & Command Reference

### Greenfield Project (Start to Deploy)
```
1. Write BRD.md
2. Invoke: project-orchestrator (input: BRD, deploy: true)
3. Review architecture diagram in projects/<slug>/diagrams/
4. Orchestrator handles phases 1–5
5. Post-deployment: invoke project-cost-analyzer and project-observability-advisor
```

### Modernize Legacy Java App
```
1. Invoke: modernization-to-factory (input: legacy codebase)
2. Review generated BRD in projects/<slug>/BRD.md
3. Invoke: project-orchestrator (input: generated BRD, deploy: true)
4. Phases 1–5 execute
5. Post-deploy: run modernization-integration-tests (Layer 1–4 validation)
```

### Add Feature to Existing Project
```
1. Update BRD.md with new feature
2. Invoke: project-orchestrator (input: updated BRD, update: true, slug: <project-slug>)
3. Orchestrator generates targeted implementation changes
4. Review diff and approve
5. Merge and deploy updated code/infra
```

### Pre-Deployment Cost & Compliance Review
```
1. Review infra parameters
2. Invoke: security-compliance-auditor (fix critical findings)
3. Review pre-deployment estimates from project-orchestrator and IaC plan output
4. Team approves cost and compliance at Gate 4.5
5. Proceed to deployment
```

### Post-Deployment Observability Audit
```
1. App running for 48–72 hours
2. Invoke: project-observability-advisor
3. Review findings and configure missing alerts/dashboards
4. Invoke: project-traceability-advisor (generate coverage report)
5. Sign-off on operational readiness
```

---

## 14. Key Principles

1. **BRD is the Contract** — Architecture, code, and infra all flow from BRD; changes ripple via orchestrator updates.
2. **Diagram as Source of Truth** — For generated project implementation, keep `projects/<slug>/diagrams/` synchronized with code and infra; for repo-level architecture governance, treat `diagrams/` as authoritative. Use `source-code-maintainer` to detect and fix drift.
3. **Quality Gates Drive Confidence** — Every phase boundary includes a validation checkpoint; no skipping approval gates.
4. **Requirement Traceability** — Every user-facing feature, infrastructure capability, and critical architectural decision traces back to a BRD requirement (REQ-ID); enables change impact analysis.
5. **Least-Privilege Security** — Managed identity + RBAC + Key Vault are mandatory; no secrets in source; audit logging always on.
6. **Cost & Observability First-Class** — Budget and monitoring are not afterthoughts; integrate pre-deployment estimates and post-deploy audits into the workflow.

---

## 15. Further Reading

- [BRD & Architecture Governance](BRD_READINESS_GATE.md)
- [Cost Estimation Guide](COST_ESTIMATION_GUIDE.md)
- [Observability Guide](OBSERVABILITY_GUIDE.md)
- [Resilience Guide](RESILIENCE_GUIDE.md)
- [Traceability Guide](TRACEABILITY_GUIDE.md)
- [App Modernization Guide](APP_MODERNIZATION_GUIDE.md)
- [Quick Start Guide](QUICKSTART.md)
