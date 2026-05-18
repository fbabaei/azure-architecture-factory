# AKS Microservices Demo

This project provides a runnable Python microservice application and Azure AKS infrastructure template generated for Azure Architecture Factory demos.

## Project Structure

- `src/api_gateway/main.py` - API gateway service that composes downstream calls.
- `src/api_gateway/templates/index.html` - storefront UI served by the gateway.
- `src/catalog_service/main.py` - Product catalog service.
- `src/order_service/main.py` - Order intake service.
- `src/payment_service/main.py` - Payment authorization service.
- `src/shared_lib/*` - shared config and model types.
- `infra/main.bicep` - entrypoint for AKS + ACR + Key Vault + Log Analytics.
- `infra/modules/*` - modular AKS infrastructure resources.

## Local Run (real application)

1. Install dependencies:
   - `pip install -r projects/aks-microservices-demo/requirements.txt`
2. Set Python path:
   - `set PYTHONPATH=projects/aks-microservices-demo/src`
3. Start services in separate terminals:
   - `uvicorn catalog_service.main:app --port 8011`
   - `uvicorn order_service.main:app --port 8012`
   - `uvicorn payment_service.main:app --port 8013`
   - `set AKS_DEMO_CATALOG_URL=http://127.0.0.1:8011`
   - `set AKS_DEMO_ORDER_URL=http://127.0.0.1:8012`
   - `set AKS_DEMO_PAYMENT_URL=http://127.0.0.1:8013`
   - `uvicorn api_gateway.main:app --port 8010`
4. Open storefront:
   - `http://localhost:8010/`
5. Open gateway health endpoint:
   - `http://localhost:8010/health`

## Azure Deployment (Bicep)

1. Choose a resource group in Azure.
2. Deploy dev parameters:
   - `az deployment group create --resource-group <rg-name> --template-file projects/aks-microservices-demo/infra/main.bicep --parameters projects/aks-microservices-demo/infra/params/dev.bicepparam`

## Kubernetes Manifests (AKS Workload Deployment)

- Base manifests: `projects/aks-microservices-demo/k8s/base`
- Environment overlays:
  - `projects/aks-microservices-demo/k8s/overlays/dev`
  - `projects/aks-microservices-demo/k8s/overlays/prod`

### Deploy to AKS (dev overlay)

1. Get AKS credentials:
   - `az aks get-credentials --resource-group <rg-name> --name <aks-cluster-name> --overwrite-existing`
2. Replace placeholder image names (`REPLACE_WITH_ACR/...`) in overlay files.
3. Apply manifests:
   - `kubectl apply -k projects/aks-microservices-demo/k8s/overlays/dev`
4. Verify rollout:
   - `kubectl get pods -n aks-micro-demo`
   - `kubectl get svc,ingress,hpa -n aks-micro-demo`

### Deploy to AKS (prod overlay)

- `kubectl apply -k projects/aks-microservices-demo/k8s/overlays/prod`

## Container Build and Push

### Service Dockerfiles

- `src/api_gateway/Dockerfile`
- `src/catalog_service/Dockerfile`
- `src/order_service/Dockerfile`
- `src/payment_service/Dockerfile`

### Build and push to ACR

Use the PowerShell helper:

- `powershell -ExecutionPolicy Bypass -File projects/aks-microservices-demo/scripts/build-and-push.ps1 -AcrLoginServer <your-acr>.azurecr.io -Tag dev`

This script builds and pushes all four services:

- `api-gateway`
- `catalog-service`
- `order-service`
- `payment-service`

## GitHub Actions CI/CD

Workflow file:

- `.github/workflows/aks-microservices-demo.yml`

Required repository secret:

- `AZURE_CREDENTIALS`

Required repository variables:

- `ACR_LOGIN_SERVER`
- `AZURE_RESOURCE_GROUP`
- `AKS_CLUSTER_NAME`

Workflow behavior:

1. Logs into Azure
2. Logs into ACR
3. Builds and pushes all service images
4. Sets AKS context
5. Rewrites placeholder image prefixes in the selected overlay
6. Applies manifests with `kubectl apply -k`
7. Waits for rollout completion

## Notes

- AKS module enables workload identity and Azure Policy addon.
- ACR pull permissions are granted to AKS managed identity.
- Use GitOps tooling (Flux or Argo CD) to deploy Kubernetes manifests for these services.
