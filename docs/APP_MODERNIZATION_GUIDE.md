# App Modernization with the Azure Architecture Factory

**Version:** 1.0  
**Date:** April 2026

---

## What Is App Modernization?

App modernization is the process of re-platforming, re-architecting, or re-building an existing application to run on a modern cloud-native infrastructure. The goal is not to rewrite for its own sake — it is to eliminate operational debt, enable elastic scaling, improve security posture, and reduce the time between code change and production delivery.

Common modernization drivers:

| Driver | Example |
|---|---|
| Aging runtime | Java 8 / .NET Framework 4.x no longer supported or maintained |
| Deployment bottleneck | Manual deployments, no CI/CD, single-environment config |
| Scaling ceiling | Monolith cannot scale individual components independently |
| Security debt | Hardcoded secrets, missing TLS, outdated auth patterns (Basic Auth, LDAP) |
| Observability gap | No structured logs, no metrics, no distributed tracing |
| Cloud vendor lock-in migration | Moving from AWS Lambda / GCP Cloud Run to Azure |

---

## What the Factory Can Do

The `modernization-to-factory` agent bridges the gap between an existing legacy codebase and a full Azure project baseline. It runs entirely within VS Code via GitHub Copilot Chat.

### What It Does Automatically

| Capability | Detail |
|---|---|
| **Technology detection** | Reads manifests (`pom.xml`, `*.csproj`, `requirements.txt`, `package.json`) and source files to identify runtime, framework, and build system |
| **Architecture pattern identification** | Detects monolith, modular monolith, microservices, serverless, or desktop app patterns |
| **Modernization debt analysis** | Identifies hardcoded secrets, missing health checks, absent CI/CD, single-environment configuration, and lack of observability instrumentation |
| **Migration risk assessment** | Classifies each component as Low / Medium / High risk with a mitigation note |
| **Azure target service mapping** | Maps each legacy component to the most appropriate Azure service — no manual service selection needed |
| **Modernization assessment document** | Writes `projects/<slug>/docs/modernization-assessment.md` with full evidence from the codebase |
| **Target-state BRD generation** | Produces a complete `projects/<slug>/docs/requirements.md` covering functional requirements, NFRs, service boundaries, and success criteria |
| **Full factory pipeline** | Delegates the BRD to `project-orchestrator`, which generates the architecture diagram, Python service scaffolding, Bicep infrastructure modules, production readiness checklist, and optional Azure deployment |

### Supported Technology Stacks

The agent can assess and map all of the following. If the technology is not listed, it will attempt auto-detection and fall back gracefully:

- Java (Spring Boot, Spring MVC, Quarkus)
- .NET (ASP.NET MVC, ASP.NET Core, Azure Functions v3/v4)
- Python (Flask, FastAPI, Django, Azure Functions)
- Node.js (Express, NestJS, Azure Functions)
- AWS Lambda (Python, Node.js, Java runtimes)

### Azure Services the Factory Targets

| Legacy pattern | Azure target |
|---|---|
| HTTP REST API | Azure Container Apps or Azure App Service |
| Background workers / batch jobs | Azure Container Apps Jobs or Azure Functions (timer/queue trigger) |
| Message queues / event buses | Azure Service Bus (queues + topics) or Azure Event Hubs |
| Relational databases | Azure SQL Database or Azure Database for PostgreSQL |
| NoSQL / document stores | Azure Cosmos DB |
| File / blob storage | Azure Blob Storage |
| Cache layer | Azure Cache for Redis |
| Authentication / identity | Microsoft Entra ID + Managed Identity |
| Configuration and secrets | Azure App Configuration + Azure Key Vault |
| Observability | Azure Monitor + Application Insights + Log Analytics |
| Container images | Azure Container Registry |
| Network isolation | Azure Virtual Network + Private Endpoints |

---

## What the Factory Cannot Do (Must Be Done Outside)

The factory generates the **target-state baseline** — the architecture, scaffolding, infrastructure, and production readiness plan for the modernized system. It does **not** perform the live migration or operational cutover. The following activities must happen outside the factory:

### 1. Actual Code Conversion

The factory scaffolds the Azure-target service structure and generates stub implementations. It does **not** automatically translate existing business logic line-by-line into the new language or framework.

**What you need to do:**  
Use the factory's scaffolded service structure as the target, then port or rewrite business logic into that structure. For Java and .NET upgrades, use the dedicated `modernize-java-upgrade` or `modernize-dotnet` agents which perform incremental in-place code transformations.

### 2. Data Migration

The factory identifies the target data stores and generates Bicep to provision them. It does **not** migrate data from the legacy database to the Azure target.

**What you need to do:**  
Use Azure Database Migration Service (for SQL workloads), AzCopy (for blob/file migrations), or a custom ETL pipeline. The factory's production readiness checklist will flag this as a required pre-deployment step.

### 3. Security Remediation of Existing Code

The factory detects hardcoded secrets and missing auth patterns in the assessment. It does **not** automatically scan and patch all CVE vulnerabilities in existing dependencies.

**What you need to do:**  
Use `modernize-java-security` or `modernize-dotnet` security scanning agents, which perform dependency audits and apply CVE fixes. Run these before or alongside the factory pipeline.

### 4. Network Topology and Private Connectivity Design

The factory generates a basic VNet + Private Endpoint Bicep module when isolation is required. It does **not** design complex hub-spoke topologies, ExpressRoute connections, or multi-region network architectures.

**What you need to do:**  
Use the `azure-enterprise-infra-planner` agent or engage a cloud networking specialist for complex network topologies that span multiple subscriptions or on-premises environments.

### 5. Legacy Integration Rewiring

The factory identifies external integrations (third-party APIs, SaaS connectors, on-premises systems) in the assessment and notes them as integration boundaries. It does **not** create new integration adapters or rewrite integration contracts.

**What you need to do:**  
Design and implement integration adapters manually, using Azure API Management, Azure Logic Apps, or custom adapter services within the scaffolded service structure.

### 6. Load and Performance Testing

The factory generates observability infrastructure (Application Insights, Log Analytics) and readiness checklists. It does **not** run load tests or baseline the legacy system's performance characteristics before cutover.

**What you need to do:**  
Use Azure Load Testing to baseline and validate the modernized system before switching production traffic. The production readiness checklist generated by the factory will include this as a gate.

### 7. Cutover and Traffic Migration

The factory generates deployment infrastructure and optional deployment execution. It does **not** manage traffic switching, Blue-Green rollout orchestration, or live database cutover.

**What you need to do:**  
Plan the cutover strategy (feature flags, parallel-run period, traffic weighting via Azure Front Door or Container Apps traffic splitting). Coordinate with the team on rollback criteria before go-live.

### 8. Incremental / Strangler-Fig Migration Phasing

The factory generates a complete target-state project in one pass. It does **not** generate incremental phased migration plans where individual services are extracted one at a time from a running monolith.

**What you need to do:**  
Break the migration into phases manually using the factory's component inventory and risk register as input. Run the factory once per phase with a scoped BRD for each extracted service boundary.

---

## Recommended Workflow

```
1. Run modernization-to-factory
   └─ Produces: assessment, BRD, architecture diagram,
                service scaffold, Bicep infra, readiness checklist

2. Review the Migration Risk Register in requirements.md
   └─ Address High-risk items before code porting begins

3. Port business logic into the factory's scaffolded service structure
   └─ Use modernize-java-upgrade / modernize-dotnet for automated transforms

4. Run security remediation (modernize-java-security or equivalent)

5. Provision Azure infrastructure
   └─ az containerapp update / az deployment group create
   └─ Or: use azure-project-deployer to deploy the Bicep modules

6. Migrate data to Azure target stores

7. Wire legacy integrations into the new Azure-hosted service boundaries

8. Run Application Insights smoke tests and Azure Load Testing baselines

9. Execute cutover with rollback criteria agreed in advance
```

---

## Related Agents

| Agent | Purpose |
|---|---|
| `modernization-to-factory` | **Entry point** — assess legacy app, generate BRD, run factory |
| `project-orchestrator` | Full factory pipeline from BRD to deployment |
| `modernize-java-upgrade` | In-place Java version and Spring Boot upgrade |
| `modernize-java-security` | CVE scanning and dependency remediation for Java |
| `modernize-dotnet` | .NET upgrade and modernization |
| `azure-cloud-migrate` | Cross-cloud migration assessment (AWS → Azure, GCP → Azure) |
| `azure-enterprise-infra-planner` | Enterprise network topology and landing zone design |
| `production-environment-advisor` | Production readiness checklist for the modernized target |
| `bicep-infrastructure-validator` | Validate and self-heal the generated Bicep modules |

---

## Related Documentation

- [QUICKSTART.md](QUICKSTART.md) — how to run the factory agents
- [USE_CASES_AND_PROBLEMS_SOLVED.md](USE_CASES_AND_PROBLEMS_SOLVED.md) — full use case catalog including Use Case 7: Legacy Application Modernization
- [BRD_READINESS_GATE.md](BRD_READINESS_GATE.md) — what makes a BRD suitable for factory processing
- [.github/agents/modernization-to-factory.agent.md](../.github/agents/modernization-to-factory.agent.md) — full agent definition and phase documentation
