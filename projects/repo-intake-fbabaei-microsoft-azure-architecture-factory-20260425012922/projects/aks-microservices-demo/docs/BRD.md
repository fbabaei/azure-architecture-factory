# Business Requirements Document (BRD)
## AKS Microservices Demo Platform

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Date** | March 30, 2026 |
| **Status** | APPROVED |
| **Prepared For** | Engineering Leadership, Cloud Architecture, Platform Engineering |
| **Sponsor** | VP of Engineering |

---

## 1. Executive Summary

The **AKS Microservices Demo Platform** is a production-grade, containerised microservices application deployed on Azure Kubernetes Service (AKS). It demonstrates how to build, deploy, and operate a horizontally scalable Python microservices architecture using Azure-native tooling — including AKS with workload identity, Azure Container Registry (ACR), Azure Application Gateway Ingress, Key Vault, Log Analytics, and GitHub Actions CI/CD.

The platform serves two purposes:
1. **Reference architecture** — a repeatable, opinionated baseline for new microservice engineering initiatives
2. **Live demo environment** — a running storefront that validates the full Azure deployment pipeline from code to production

---

## 2. Business Problem Statement

### 2.1 No Standard Microservices Baseline
**Problem:** Engineering teams starting new microservice projects build from scratch: Docker setup, Kubernetes manifests, AKS configuration, RBAC, ingress, autoscaling, observability — all reinvented per project.

**Impact:**
- 4–8 weeks of infrastructure setup before a single line of business logic is written
- Inconsistent cluster configuration (security gaps, no autoscaling, no structured logging)
- High cognitive load — engineers must be Kubernetes experts before shipping features

**Root Cause:** No approved, battle-tested AKS microservices template exists in the organization.

---

### 2.2 Inconsistent Container Security Posture
**Problem:** Microservice deployments use long-lived credentials, unrestricted container registries, and overly permissive RBAC.

**Impact:**
- Container image pull from unauthenticated registries (supply chain risk)
- Secrets embedded in environment variables (credential leakage risk)
- No workload identity — services use shared keys rather than managed identity

**Root Cause:** Security patterns are not codified into deployable templates; each team applies them inconsistently.

---

### 2.3 Poor Observability Out of the Box
**Problem:** New AKS deployments have no structured logging, no metrics pipeline, and no alerts configured by default.

**Impact:**
- Production incidents with no visible root cause
- Manual `kubectl logs` investigation across pods
- SLA breaches go undetected until users report them

**Root Cause:** Observability is treated as a Day-2 concern, not a Day-0 requirement.

---

### 2.4 No CI/CD for Container Workloads
**Problem:** Teams build Docker images manually, push to ACR ad-hoc, and apply Kubernetes manifests by hand.

**Impact:**
- Deployments are not repeatable or auditable
- No rollback strategy when deployments fail
- Long deployment lead times (hours to days)

**Root Cause:** No standardised CI/CD pipeline template for containerised workloads on AKS.

---

## 3. Business Opportunity

### 3.1 Organisational Context
- Container adoption is accelerating: 60%+ of new services targeting Kubernetes
- AKS is the approved standard for container orchestration
- Engineering teams waste 40–60% of project setup time on boilerplate infrastructure

### 3.2 Competitive / Internal Landscape

| Approach | Time to Production | Security | Observability | Repeatability | Verdict |
|---|---|---|---|---|---|
| Manual per-project setup | 4–8 weeks | Inconsistent | None by default | Low | Status quo — unsustainable |
| Helm charts (community) | 2–4 weeks | Partial | Partial | Medium | Not Azure-native |
| Azure-managed templates (this) | < 1 week | Best practice | Built-in | High | **✓ Target state** |

### 3.3 Value Proposition

| Audience | Value |
|---|---|
| **Application Engineers** | Focus on business logic; skip 4–8 weeks of Kubernetes boilerplate |
| **Platform / DevOps Engineers** | One approved, secure, observable AKS baseline to maintain |
| **Security / CISO** | Workload identity, ACR pull RBAC, Key Vault — enforced by default |
| **Engineering Leadership** | Faster product delivery; consistent, auditable deployments |
| **FinOps** | HPA-driven autoscaling prevents over-provisioning; cost-proportional scaling |

---

## 4. Business Objectives & Key Results (OKRs)

### Objective 1: Reduce Microservice Project Setup Time

| KR | Target | Timeline |
|---|---|---|
| KR1.1 — Reduce infrastructure setup time per new project | 4–8 weeks → < 1 week | 3 months |
| KR1.2 — Template adoption across eligible new projects | > 75% | 6 months |
| KR1.3 — Time from code commit to production | Manual days → < 15 minutes (CI/CD) | 3 months |
| KR1.4 — Engineer onboarding to first deployment | 2+ days → < 4 hours | 6 months |

### Objective 2: Enforce Security Best Practices

| KR | Target | Timeline |
|---|---|---|
| KR2.1 — Workload identity adoption | 100% of services use managed identity | 3 months |
| KR2.2 — Eliminate embedded secrets | 0 secrets in manifests, env vars, or Dockerfiles | 3 months |
| KR2.3 — ACR pull via RBAC (no admin credential) | 100% of AKS → ACR connections | 3 months |
| KR2.4 — Azure Policy addon enabled | 100% of clusters | 3 months |

### Objective 3: Achieve Full Observability from Day 0

| KR | Target | Timeline |
|---|---|---|
| KR3.1 — Log Analytics connected to all clusters | 100% | 3 months |
| KR3.2 — Structured logs from all services | 100% of pods | 3 months |
| KR3.3 — MTTR for production incidents | > 2 hours → < 20 minutes | 6 months |
| KR3.4 — Alerting: CPU, memory, pod restarts | 100% of workloads | 6 months |

### Objective 4: Standardise CI/CD for Container Workloads

| KR | Target | Timeline |
|---|---|---|
| KR4.1 — Automated image build + push per commit | 100% of services | 3 months |
| KR4.2 — Automated manifest apply per merge to main | 100% of environments | 3 months |
| KR4.3 — Rollout verification (wait for rollout) | Built into CI/CD | 3 months |
| KR4.4 — Environment-specific overlays (dev/prod) | Both environments templated | 3 months |

---

## 5. Stakeholder Analysis

| Stakeholder | Interest | Impact | Influence | Strategy |
|---|---|---|---|---|
| Application Engineers | Fast start, simple local dev | High | High | Clear README; local run in < 5 mins |
| Platform / DevOps Engineers | Maintainability, security, consistency | High | High | Modular Bicep; environment overlays |
| Security / CISO | Workload identity, RBAC, no secrets in manifests | High | High | Built-in from day 0; policy addon |
| Engineering Leadership | Delivery speed, quality, cost | High | High | Adoption metrics; time-to-deploy KRs |
| FinOps | HPA, right-sized nodes, cost attribution | Medium | Medium | HPA configured; resource requests/limits set |
| SRE / Cloud Ops | Observability, incident response | High | Medium | Log Analytics; structured logging; alerts |

---

## 6. Business Impact & ROI

### 6.1 Cost of Status Quo (Per New Microservice Project)

| Cost Source | Per-Project Cost |
|---|---|
| Infrastructure setup (engineer time: 6 weeks × $4K/week) | $24,000 |
| Security remediation (ad-hoc fixes post-launch) | $10,000 |
| Observability gaps (incident MTTR cost: 3 incidents × 4 hrs × $2K/hr) | $24,000 |
| Manual deployment overhead (2 hrs/deployment × 20 deployments/month × $150/hr) | $72,000/yr |
| **Total per-project Year 1** | **~$130,000** |

### 6.2 Cost With This Template (Per New Project)

| Cost Source | Per-Project Cost |
|---|---|
| Template adoption + customisation (1 week × $4K) | $4,000 |
| AKS + ACR + Key Vault (Consumption, dev cluster) | $8,000/yr |
| CI/CD maintenance | $5,000/yr |
| **Total per-project Year 1** | **~$17,000** |

**Savings per project: ~$113,000 (87% reduction)**  
**Across 5 new projects/year: ~$565,000 annual savings**

### 6.3 ROI Summary

| | Value |
|---|---|
| Annual savings (5 projects) | $565,000 |
| Template build investment (already complete) | $40,000 |
| **ROI Year 1** | **1,313% (14× return)** |
| **Payback period** | **< 1 month** |

---

## 7. Strategic Alignment

| Organisational Goal | How This Platform Addresses It |
|---|---|
| Cloud-First on AKS | Production-grade AKS baseline with all Azure-native integrations |
| Zero-Trust Security | Workload identity, ACR RBAC, Key Vault, Azure Policy addon |
| Developer Productivity | Template eliminates 4–8 weeks of boilerplate; local dev in minutes |
| Continuous Delivery | GitHub Actions CI/CD: build → push → deploy → verify in < 15 mins |
| Cost Efficiency | HPA autoscaling; node pool right-sizing; no always-on over-provision |

---

## 8. Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Teams fork and diverge (template drift) | Medium | High | Central ownership; versioned releases; periodic sync |
| AKS version upgrades break manifests | Medium | Medium | Test upgrades in dev overlay first; pin API versions |
| ACR image pull failures (RBAC misconfigured) | Low | High | IaC-enforced role assignment; pre-deploy validation |
| HPA misconfiguration (thrashing) | Low | Medium | Tested HPA thresholds; stabilisation window configured |
| GitHub Actions secret (`AZURE_CREDENTIALS`) leaked | Low | High | Use federated identity (OIDC) instead of long-lived secret |
| Node pool exhaustion under load | Low | High | Cluster autoscaler enabled; resource quotas per namespace |

---

## 9. Success Measures & Monitoring

### 9.1 Quantitative Metrics (Per Quarter)

| Metric | Current | 3-Month Target | 6-Month Target |
|---|---|---|---|
| New projects using template (%) | 0% | 50% | 75%+ |
| Time from commit to production | Manual, hours-days | < 15 min | < 10 min |
| Infrastructure setup time (new project) | 4–8 weeks | 1 week | < 1 week |
| MTTR for production incidents | 2+ hours | 45 min | < 20 min |
| Secrets embedded in manifests | Unknown | 0 | 0 |
| Log Analytics coverage (% of pods) | 0% | 100% | 100% |

### 9.2 Qualitative Feedback (Quarterly)
1. "How quickly could you get a new service deployed using this template?" (1–10)
2. "What was the hardest part of adopting the template?" (open)
3. "Would you recommend this template to another team?" (NPS)

---

## 10. Implementation Roadmap

| Phase | Timeline | Goals | Deliverables |
|---|---|---|---|
| **Phase 1: Core Template** | Weeks 1–4 | AKS + ACR + Key Vault + Log Analytics Bicep; 4 Python services; base K8s manifests | Working local dev; Bicep deployment |
| **Phase 2: CI/CD** | Weeks 5–6 | GitHub Actions: build, push, deploy, verify | `.github/workflows/aks-microservices-demo.yml` |
| **Phase 3: Overlays & HPA** | Weeks 7–8 | Dev/prod overlays; HPA; ingress (AGIC); namespace isolation | Environment-specific manifests; autoscaling |
| **Phase 4: Security Hardening** | Weeks 9–10 | Workload identity; Azure Policy addon; OPA constraints | Zero embedded secrets; policy-compliant cluster |
| **Phase 5: Rollout** | Months 3–6 | Team onboarding; adoption tracking; feedback loop | Training; 75%+ adoption target |

**V2 Roadmap:**
- GitOps with Flux or Argo CD (replace `kubectl apply` in CI/CD)
- OIDC federated identity for GitHub Actions (eliminate `AZURE_CREDENTIALS` secret)
- Service mesh (Istio / Linkerd) for mTLS between services
- Distributed tracing with OpenTelemetry → Application Insights

---

## 11. Funding & Resources

### 11.1 Budget Summary

| Category | Year 1 Cost |
|---|---|
| Development (already complete) | $0 |
| AKS cluster (dev, Standard_D2s_v3 × 2 nodes) | $5,000/yr |
| ACR (Basic tier) | $600/yr |
| Log Analytics + Key Vault | $2,000/yr |
| Training & documentation | $10,000 |
| Maintenance (0.25 FTE) | $25,000 |
| **Total Year 1** | **$42,600** |
| **Ongoing Annual** | **$32,600** |

### 11.2 Staffing

| Role | Year 1 | Ongoing |
|---|---|---|
| Platform Engineer (owner) | 0.5 FTE | 0.25 FTE |
| Security Review | 0.25 FTE | 0.1 FTE |
| Documentation | 0.1 FTE | 0.05 FTE |

---

## 12. Go / No-Go Criteria

### Approve If:
- ✅ Local dev stack starts in < 5 minutes
- ✅ Full Bicep deployment completes without errors in dev environment
- ✅ CI/CD pipeline deploys all 4 services to AKS in < 15 minutes
- ✅ HPA scales API gateway from 2 → 4 replicas under synthetic load
- ✅ Log Analytics receives structured logs from all pods
- ✅ Zero secrets embedded in manifests or Dockerfiles

### Escalate If:
- ❌ Template adoption < 30% after 6 months
- ❌ Security review finds critical vulnerabilities post-launch
- ❌ CI/CD pipeline failure rate > 10%

---

## 13. Approvals

| Role | Decision | Date |
|---|---|---|
| Sponsor — VP of Engineering | ✅ APPROVED | March 30, 2026 |
| Security Review — CISO | ✅ APPROVED | March 30, 2026 |
| Platform Engineering Lead | ✅ APPROVED | March 30, 2026 |
| FinOps — Finance Director | ✅ APPROVED | March 30, 2026 |

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **AKS** | Azure Kubernetes Service — managed Kubernetes cluster on Azure |
| **ACR** | Azure Container Registry — private Docker image registry on Azure |
| **AGIC** | Application Gateway Ingress Controller — routes external HTTP(S) traffic into AKS |
| **HPA** | Horizontal Pod Autoscaler — automatically scales pods based on CPU/memory metrics |
| **Workload Identity** | Kubernetes workload identity federation — passwordless Azure service access from pods |
| **Kustomize** | Kubernetes configuration management tool — applies environment-specific overlays to base manifests |
| **Overlay** | Environment-specific manifest patch (dev/prod) applied on top of base K8s manifests |
| **Managed Identity** | Azure-native passwordless identity for service-to-service authentication |
| **GitOps** | Practice of using Git as the single source of truth for cluster state (Flux, Argo CD) |
| **MTTR** | Mean Time to Recover — how long to detect and resolve a production incident |
