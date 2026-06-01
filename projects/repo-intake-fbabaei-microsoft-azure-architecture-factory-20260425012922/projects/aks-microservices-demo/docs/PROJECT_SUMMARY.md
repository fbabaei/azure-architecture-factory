# AKS Microservices Demo — One-Page Summary

**Version:** 1.0 | **Date:** March 30, 2026 | **Status:** Implementation Complete

---

## What It Is

A **production-grade, containerised Python microservices application** deployed on Azure Kubernetes Service (AKS). It is both a runnable storefront demo and an approved organisational reference architecture for new microservice projects — eliminating 4–8 weeks of Kubernetes boilerplate per new service initiative.

---

## Business Problem Solved

| Pain Point | Impact Before |
|---|---|
| No standard AKS baseline — every project starts from scratch | 4–8 weeks of infra setup before first line of business logic |
| Inconsistent security (embedded secrets, unrestricted ACR, no workload identity) | Supply chain risk; credential leakage; policy violations |
| No observability by default (no Log Analytics, no structured logs) | Production incidents with no root cause visibility; hours to MTTR |
| Manual Docker build, ACR push, and `kubectl apply` | Non-repeatable deployments; no rollback; hours per release |

---

## Architecture Overview

```
                          ┌──────────────────────────────────────────────────────────────┐
  Internet                │                  AKS CLUSTER (aks-micro-demo)                │
     │                    │                                                              │
     ▼                    │  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
  Azure Application  ────►│  │ API Gateway  ├──►│Catalog Service│   │  Order Service   │  │
  Gateway (AGIC)          │  │ (port 80)   │   │  (port 8011)  │   │  (port 8012)     │  │
  Ingress                 │  │ HPA: 2–8    │   └──────────────┘   └──────────────────┘  │
                          │  │ replicas    │   ┌──────────────┐                          │
                          │  └─────────────┘   │Payment Service│                         │
                          │                    │  (port 8013)  │                         │
                          │                    └──────────────┘                          │
                          └─────────────────────────┬────────────────────────────────────┘
                                                    │
                    ┌───────────────────────────────┼────────────────────────────┐
                    │                               │                            │
               ┌────▼──────┐               ┌────────▼────────┐        ┌─────────▼──────┐
               │    ACR    │               │   Key Vault      │        │ Log Analytics  │
               │ (images)  │               │   (secrets)      │        │  (observability)│
               └───────────┘               └─────────────────┘        └────────────────┘
```

---

## Microservice Breakdown

| Service | Port | Responsibility |
|---|---|---|
| `api_gateway` | 8010 | Storefront UI + API composition; routes to catalog, order, payment |
| `catalog_service` | 8011 | Product catalogue — list products, get product details |
| `order_service` | 8012 | Order intake — create and retrieve orders |
| `payment_service` | 8013 | Payment authorisation — validate and confirm payment |
| `shared_lib` | — | Shared config, data models, health check helpers |

---

## Key Azure Resources

| Resource | SKU / Config | Role |
|---|---|---|
| Azure Kubernetes Service (AKS) | Standard; workload identity enabled; Azure Policy addon | Container orchestration; pod identity; policy enforcement |
| Azure Container Registry (ACR) | Basic | Private Docker image storage; RBAC pull to AKS managed identity |
| Azure Key Vault | Standard | Secrets — connection strings, API keys; no embedded credentials |
| Log Analytics Workspace | Pay-as-you-go | Structured log aggregation; AKS diagnostic settings |
| Azure Application Gateway (AGIC) | Ingress controller | Routes external HTTP(S) to `api-gateway` service |
| Azure Monitor | Standard | Alerts: CPU, memory, pod restart rate |

---

## Kubernetes Manifest Structure

| Manifest | Purpose |
|---|---|
| `namespace.yaml` | Isolated namespace `aks-micro-demo` |
| `configmap.yaml` | Shared environment config (service URLs, log level) |
| `api-gateway.yaml` | Deployment + ClusterIP service for API Gateway |
| `catalog.yaml` | Deployment + ClusterIP service for Catalog Service |
| `order.yaml` | Deployment + ClusterIP service for Order Service |
| `payment.yaml` | Deployment + ClusterIP service for Payment Service |
| `hpa.yaml` | HPA for API Gateway: 2–8 replicas at 70% CPU |
| `ingress.yaml` | AGIC ingress rule routing `aks-micro.local → api-gateway:80` |
| `overlays/dev` | Dev-specific resource limits and replica counts |
| `overlays/prod` | Prod-specific resource limits and replica counts |

---

## CI/CD Pipeline (GitHub Actions)

```
Code Push → Build Docker Images (4 services) → Push to ACR → Get AKS Credentials
→ Rewrite image tags in overlay → kubectl apply -k overlays/{env} → Wait for rollout ✓
```

| Step | Tool |
|---|---|
| Authenticate to Azure | `azure/login` with `AZURE_CREDENTIALS` |
| Log into ACR | `az acr login` |
| Build + push images | `docker build` + `docker push` |
| Get AKS kubeconfig | `az aks get-credentials` |
| Deploy manifests | `kubectl apply -k overlays/{env}` |
| Verify rollout | `kubectl rollout status` |

---

## Infrastructure as Code (Bicep)

| Module | Resource Provisioned |
|---|---|
| `modules/compute/aks.bicep` | AKS cluster; workload identity; ACR pull role assignment |
| `modules/compute/acr.bicep` | Azure Container Registry |
| `modules/security/keyvault.bicep` | Key Vault with access policies |
| `modules/monitoring/log-analytics.bicep` | Log Analytics Workspace |
| `infra/main.bicep` | Orchestrates all modules; outputs cluster name, ACR login server |
| `params/dev.bicepparam` | Dev environment parameters |

---

## Cross-Cutting Capabilities

| Capability | Implementation |
|---|---|
| **Security** | Workload identity; ACR pull via managed identity RBAC; Key Vault; Azure Policy addon |
| **Autoscaling** | HPA on API Gateway (2–8 replicas at 70% CPU); Cluster Autoscaler |
| **Observability** | Log Analytics Workspace; AKS diagnostic settings; structured pod logs |
| **Environment Isolation** | Kustomize overlays (dev / prod); separate namespace |
| **IaC** | Modular Bicep — one command deploys entire infrastructure stack |
| **CI/CD** | GitHub Actions — commit-to-production in < 15 minutes |

---

## Non-Functional Requirements

| Requirement | Target | Mechanism |
|---|---|---|
| Deployment Pipeline Duration | < 15 minutes commit-to-production | GitHub Actions parallel build |
| API Gateway Availability | ≥ 99.9% | HPA min 2 replicas; health probes |
| Autoscaling Response | Pod scale-out in < 2 minutes | HPA CPU threshold 70% |
| Zero embedded secrets | 100% | Key Vault; no env vars with secrets in manifests |
| Structured logging | 100% of pods | Log Analytics; stdout JSON logging |
| Security policy compliance | 100% | Azure Policy addon; OPA Gatekeeper |

---

## ROI at a Glance

| | Value |
|---|---|
| Cost savings per project vs. manual setup | ~$113,000 |
| Savings across 5 new projects/year | ~$565,000/yr |
| Template build investment (already complete) | $40,000 |
| **ROI Year 1** | **1,313% (14× return)** |

---

## Project Status

| Phase | Status |
|---|---|
| 4 Python microservices + shared lib | ✅ Complete |
| Docker builds + `.dockerignore` | ✅ Complete |
| Bicep infrastructure (AKS, ACR, Key Vault, Log Analytics) | ✅ Complete |
| Kubernetes base manifests (namespace, deployments, HPA, ingress) | ✅ Complete |
| Kustomize overlays (dev / prod) | ✅ Complete |
| GitHub Actions CI/CD workflow | ✅ Complete |
| Build-and-push PowerShell script | ✅ Complete |
| Production security hardening (workload identity OIDC) | ⏳ V2 roadmap |
| GitOps (Flux / Argo CD) | ⏳ V2 roadmap |
