# AKS Microservices Demo

This sample represents a platform-oriented AKS project output for Azure Architecture Factory.

## What this sample includes

- `diagrams/` architecture source artifacts for the AKS topology
- `src/` service code for API gateway, catalog, order, and payment APIs
- `tests/` service health contract checks
- `infra/` Bicep modules and parameter files for AKS deployment
- `docs/` BRD, project summary, and implementation notes
- `k8s/` workload manifests and overlays for deployment workflows

## Quick local validation

1. Install dependencies:
   - `pip install -r projects/aks-microservices-demo/requirements.txt`
2. Run service health tests:
   - `python -m unittest discover projects/aks-microservices-demo/tests`

## Deployment path

Use `infra/main.bicep` with `infra/params/dev.bicepparam`, then deploy workloads from `k8s/overlays/dev`.
