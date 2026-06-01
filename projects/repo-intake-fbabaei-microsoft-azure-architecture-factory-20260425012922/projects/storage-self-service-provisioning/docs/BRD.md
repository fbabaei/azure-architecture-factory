# Business Requirements Document (BRD)
## Storage Self-Service Provisioning Platform

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Date** | March 30, 2026 |
| **Status** | APPROVED |
| **Prepared For** | Data Platform Leadership, Cloud Operations, Security & Compliance |
| **Sponsor** | VP of Cloud Infrastructure |

---

## 1. Executive Summary

The **Storage Self-Service Provisioning Platform** enables authorized users to request, approve, and receive Azure storage resources through a governed web portal — without filing IT tickets or waiting for manual engineering intervention. All provisioning is automated, auditable, policy-enforced, and observable.

The platform eliminates the most common bottleneck in enterprise data operations: the multi-day wait between "I need storage" and "storage is ready, tagged, secured, and catalogued." It does this while enforcing the same security, governance, and compliance standards that would otherwise require a senior engineer's involvement on every request.

---

## 2. Business Problem Statement

### 2.1 Storage Provisioning Bottleneck
**Problem:** Requesting Azure storage (Storage Accounts, ADLS Gen2 containers) requires manual engineering effort — tickets, approvals, CLI scripts, and manual Purview registration — taking 3–10 business days per request.

**Impact:**
- Project teams blocked waiting for infrastructure before data work can start
- Data engineers distracted from analytics work to handle provisioning tickets
- Inconsistent naming, tagging, and configuration across manually provisioned resources

**Root Cause:** No self-service interface or automated workflow exists; every request follows a fully manual path.

---

### 2.2 Governance & Compliance Gaps
**Problem:** Manually provisioned storage lacks consistent tagging, classification, and Purview registration. There is no traceable request-to-resource audit trail.

**Impact:**
- Failed data governance audits (no lineage from requester to resource)
- Cost allocation errors (untagged resources can't be attributed to teams)
- Compliance violations (data class not enforced at provisioning time)

**Root Cause:** Governance steps are applied inconsistently and post-hoc — not built into the provisioning workflow.

---

### 2.3 Security Posture Risks
**Problem:** Engineers provision storage using personal credentials or shared keys embedded in scripts. Secrets are not rotated and access is not scoped to least privilege.

**Impact:**
- Credential leakage risk (keys in code, tickets, emails)
- Over-privileged service accounts with broad storage access
- No centralized secret management or rotation

**Root Cause:** Lack of production-grade automation with managed identity and Key Vault integration.

---

### 2.4 Observability Gaps
**Problem:** No central system tracks provisioning request state, outcome, or failure reasons. When provisioning fails, root cause investigation is manual.

**Impact:**
- Requesters have no visibility into status (repeated follow-up tickets)
- Operations team can't proactively detect and resolve provisioning failures
- No SLA enforcement or measurement

**Root Cause:** Provisioning state is tribal knowledge — tracked in email threads, not systems.

---

## 3. Business Opportunity

### 3.1 Market & Organizational Context
- Cloud storage requests are growing 30–50% YoY as more teams adopt data-driven workflows
- Manual provisioning does not scale: each additional team adds proportional engineering burden
- Regulatory requirements (GDPR, SOC 2) demand traceable data lineage from creation to consumption

### 3.2 Competitive / Internal Landscape

| Approach | Speed | Governance | Security | Scalability | Verdict |
|---|---|---|---|---|---|
| Manual IT ticket | 3–10 days | Inconsistent | Risky | Poor | Status quo — unacceptable |
| Cloud console (manual) | 1–2 days | None | Risky | Poor | Same problems, faster |
| Terraform per project | Hours | Partial | Good | Medium | High skill barrier |
| **This Platform** | **Minutes** | **Built-in** | **Best practice** | **High** | **✓ Target state** |

### 3.3 Value Proposition

| Audience | Value |
|---|---|
| **Project Teams / Requesters** | Storage ready in minutes, not days; full status visibility |
| **Data Engineers** | Freed from provisioning tickets; consistent, reproducible infrastructure |
| **Security / Compliance** | Every resource is policy-checked, tagged, and Purview-registered before use |
| **Cloud FinOps** | All resources tagged at birth; cost attribution is automatic |
| **CTO / CIO** | Scalable platform: 10× more requests, same operational overhead |

---

## 4. Business Objectives & Key Results (OKRs)

### Objective 1: Eliminate Storage Provisioning Bottleneck

| KR | Target | Timeline |
|---|---|---|
| KR1.1 — Reduce provisioning lead time | 3–10 days → < 10 minutes | 3 months |
| KR1.2 — Eliminate manual provisioning tickets | 100% of standard requests via platform | 6 months |
| KR1.3 — Increase data engineer focus on analytics | 20% → < 5% of time spent on provisioning | 6 months |
| KR1.4 — Platform adoption across eligible teams | > 80% of teams using platform | 12 months |

### Objective 2: Enforce Governance at Provisioning Time

| KR | Target | Timeline |
|---|---|---|
| KR2.1 — Resource tagging compliance | 0% → 100% of provisioned resources tagged | 3 months |
| KR2.2 — Purview registration coverage | 0% → 100% of new storage assets registered | 3 months |
| KR2.3 — Audit trail completeness | Full request-to-resource lineage for 100% of requests | 6 months |
| KR2.4 — Policy check pass rate before provisioning | 100% (no resource created without policy clearance) | 3 months |

### Objective 3: Achieve Security Best Practices

| KR | Target | Timeline |
|---|---|---|
| KR3.1 — Embedded secrets eliminated | 0 secrets in code, tickets, or scripts | 3 months |
| KR3.2 — Managed identity coverage | 100% of service-to-service calls use managed identity | 3 months |
| KR3.3 — Secret rotation | All Key Vault secrets on automated rotation policy | 6 months |
| KR3.4 — Least-privilege RBAC | All identities scoped to minimum required permissions | 3 months |

### Objective 4: Operational Excellence & Observability

| KR | Target | Timeline |
|---|---|---|
| KR4.1 — API acknowledgment latency | < 3 seconds for all provisioning requests | 3 months |
| KR4.2 — Platform availability | ≥ 99.9% | 6 months |
| KR4.3 — Provisioning success rate | ≥ 98% (auto-retry on transient failures) | 3 months |
| KR4.4 — MTTR for provisioning failures | < 30 minutes (structured alerts + logs) | 6 months |

---

## 5. Stakeholder Analysis

| Stakeholder | Interest | Impact | Influence | Strategy |
|---|---|---|---|---|
| Project Teams / Requesters | Fast, reliable storage access | High | High | Self-service UX; real-time status |
| Data Engineers | Reduced ticket burden | High | High | Automate all standard requests |
| Cloud Operations | Operational efficiency, SLA | High | High | Structured alerts; runbooks |
| Security / CISO | Managed identity, secrets, least privilege | High | High | Built-in from day 1; audit logs |
| Compliance / Audit | Lineage, tagging, classification | High | Medium | Purview integration; full audit trail |
| FinOps / Finance | Cost attribution, tagging | Medium | Medium | Mandatory tags enforced at creation |
| CTO / CIO | Scalability, standardization | High | High | Platform-as-a-product; self-service |
| IT Operations | Reduced manual effort | Medium | Medium | Training; runbooks; handover |

---

## 6. Business Impact & ROI

### 6.1 Cost of Status Quo (Annualized, 200 Storage Requests/Year)

| Cost Source | Annual Cost |
|---|---|
| Engineer time: 4 hrs × 200 requests × $150/hr | $120,000 |
| Requester wait time (blocked projects): 2 days avg × 200 × $500/day | $200,000 |
| Compliance remediation (mis-tagged/mis-classified resources) | $80,000 |
| Security incidents (credential misuse, over-privilege) | $100,000 risk reserve |
| **Total** | **$500,000** |

### 6.2 Cost With Platform

| Cost Source | Annual Cost |
|---|---|
| Platform maintenance (0.5 FTE) | $50,000 |
| Cloud compute (Container Apps, Cosmos DB) | $15,000 |
| Training & onboarding | $10,000 |
| **Total** | **$75,000** |

**Net Annual Savings: $425,000 (85% reduction)**

### 6.3 ROI Summary

| | Value |
|---|---|
| Annual savings | $425,000 |
| Risk mitigation value (security + compliance) | $200,000 |
| **Total annual benefit** | **$625,000** |
| One-time investment (already built) | $80,000 |
| **ROI (Year 1)** | **781% (8.8× return)** |
| **Payback period** | **< 2 months** |

---

## 7. Strategic Alignment

| Organizational Goal | How This Platform Addresses It |
|---|---|
| Cloud-First Strategy | All provisioning via Azure-native services; no on-prem dependencies |
| Zero-Trust Security | Managed identity, Key Vault, least-privilege RBAC enforced by design |
| Data Governance Maturity | Every resource registered in Purview with classification at birth |
| Cost Optimization | Mandatory tags enable full FinOps attribution; scale-to-zero compute |
| Developer Productivity | Self-service eliminates ticket overhead; API-first design enables automation |

---

## 8. Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Low adoption (teams bypass platform) | Medium | High | Enforce policy: no manual provisioning without platform record |
| Azure API rate limits during high load | Low | Medium | Exponential backoff + circuit breaker in workflow worker |
| Cosmos DB / Event Grid outage | Low | High | Local fallback mode; retry queue; structured alerting |
| Purview registration failure | Low | Medium | Async registration with retry; alert on failure; manual fallback doc |
| Managed identity misconfiguration | Low | High | IaC-enforced RBAC; pre-deployment validation checklist |
| Data misclassification by requester | Medium | High | Classification validated by governance workflow before provisioning |

---

## 9. Success Measures & Monitoring

### 9.1 Quantitative Metrics (Monthly Dashboard)

| Metric | Current | 3-Month Target | 6-Month Target |
|---|---|---|---|
| Avg provisioning lead time | 3–10 days | < 1 hour | < 10 minutes |
| Requests handled via platform (%) | 0% | 60% | 100% |
| Resource tagging compliance (%) | ~40% | 100% | 100% |
| Purview registration coverage (%) | ~10% | 100% | 100% |
| Provisioning success rate (%) | N/A | 95% | 98%+ |
| API acknowledgment latency (p95) | N/A | < 3s | < 1s |
| Platform availability (%) | N/A | 99.5% | 99.9% |
| Open provisioning tickets (manual) | 200+/yr | < 20/yr | 0 |

### 9.2 Qualitative Feedback (Quarterly)
1. "How easy is it to request storage through the platform?" (1–10 NPS)
2. "How confident are you that your storage resources are properly governed?" (1–10)
3. "What friction points remain in the provisioning workflow?" (open feedback)

---

## 10. Implementation Roadmap

| Phase | Timeline | Goals | Deliverables |
|---|---|---|---|
| **Phase 1: Core Platform** | Weeks 1–4 | API + worker + local backends | Provisioning API, workflow worker, local test runner |
| **Phase 2: Azure Integration** | Weeks 5–8 | Cosmos DB, Azure Storage, Event Grid, Key Vault | Full Azure backend; managed identity auth |
| **Phase 3: Governance** | Weeks 9–12 | Purview registration, tagging policy, classification | Governance workflow; Purview connector |
| **Phase 4: Observability** | Weeks 13–16 | Azure Monitor alerts, dashboards, runbooks | Monitoring dashboard; alerting rules; runbook docs |
| **Phase 5: Rollout** | Months 4–6 | Team onboarding, adoption tracking | Training; 80%+ adoption target |

**V2 Roadmap:**
- Approval workflow with multi-level sign-off (requester → manager → ops)
- Lifecycle management (auto-decommission on project end)
- Cost estimation shown at request time
- Terraform / Bicep output export for teams that need IaC artifacts

---

## 11. Funding & Resources

### 11.1 Budget Summary

| Category | Year 1 Cost |
|---|---|
| Development (already complete) | $0 |
| Azure infrastructure (Cosmos DB, Container Apps, Event Grid) | $15,000 |
| Training & documentation | $15,000 |
| Support & maintenance (0.5 FTE) | $50,000 |
| **Total Year 1** | **$80,000** |
| **Ongoing Annual** | **$65,000** |

### 11.2 Staffing

| Role | Year 1 | Ongoing |
|---|---|---|
| Platform Engineer / Owner | 1.0 FTE | 0.5 FTE |
| Cloud Ops (runbooks, alerting) | 0.5 FTE | 0.25 FTE |
| Security review | 0.25 FTE | 0.1 FTE |

---

## 12. Go / No-Go Criteria

### Approve If:
- ✅ Provisioning API acknowledges requests in < 3 seconds
- ✅ End-to-end provisioning completes in < 10 minutes (happy path)
- ✅ 100% of test resources correctly tagged and registered in Purview
- ✅ Zero embedded secrets — all credentials via Key Vault + managed identity
- ✅ Security review passes with no critical findings

### Escalate If:
- ❌ Adoption < 40% after 3 months
- ❌ Provisioning success rate < 90%
- ❌ Any critical security finding post-launch
- ❌ Cost overruns > 25% vs. forecast

---

## 13. Approvals

| Role | Decision | Date |
|---|---|---|
| Sponsor — VP of Cloud Infrastructure | ✅ APPROVED | March 30, 2026 |
| Security Review — CISO | ✅ APPROVED | March 30, 2026 |
| Compliance — Data Governance Lead | ✅ APPROVED | March 30, 2026 |
| FinOps — Finance Director | ✅ APPROVED | March 30, 2026 |

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **Self-Service Provisioning** | Users request and receive resources through an automated platform without manual engineer involvement |
| **ADLS Gen2** | Azure Data Lake Storage Gen2 — hierarchical namespace storage for big data analytics |
| **Microsoft Purview** | Azure data governance service for cataloguing, classifying, and tracking data assets |
| **Managed Identity** | Azure-native passwordless identity for service-to-service authentication |
| **Event Grid** | Azure serverless event routing service used for provisioning lifecycle events |
| **Circuit Breaker** | Resilience pattern that stops retrying after repeated failures to prevent cascade failures |
| **Data Classification** | Labelling data assets (e.g., Public, Internal, Confidential, Restricted) to enforce access policies |
| **Least Privilege** | Principle of granting only the minimum permissions required for a task |
| **FinOps** | Financial Operations practice of tracking and optimizing cloud spend |
| **MTTR** | Mean Time to Recover — how long to detect and resolve a platform failure |
