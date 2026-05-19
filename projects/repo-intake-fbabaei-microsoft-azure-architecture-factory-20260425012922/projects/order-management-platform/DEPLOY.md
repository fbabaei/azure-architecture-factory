# OrderManagement Platform - Deployment Guide

## 🚀 Quick Deployment to Azure

### Prerequisites Check
```bash
# Verify Azure CLI installed
az --version

# Verify Bicep support
az bicep version

# Authenticate to Azure
az login

# Set subscription
az account set --subscription "<subscription-id>"
```

### One-Command Deployment

**Deploy to Dev Environment:**
```bash
# Single command to deploy everything
RESOURCE_GROUP="omp-dev-rg"
LOCATION="eastus"
ENVIRONMENT="dev"

az group create --name $RESOURCE_GROUP --location $LOCATION

az deployment group create \
  --name omp-infrastructure \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/params/${ENVIRONMENT}.bicepparam

# Save outputs
az deployment group show \
  --name omp-infrastructure \
  --resource-group $RESOURCE_GROUP \
  --query "properties.outputs" > deployment-outputs.json
```

### Deploy Container Images

```bash
#!/bin/bash
set -e

# Get outputs
ACR_NAME=$(jq -r '.containerRegistryName.value' deployment-outputs.json)
CAE_NAME=$(jq -r '.containerAppEnvironmentName.value' deployment-outputs.json)

# Build and push images
SERVICES=("api-gateway" "order-service" "inventory-service" "payment-service" "notification-service" "analytics-service")

for service in "${SERVICES[@]}"; do
  echo "Building $service..."
  az acr build \
    --registry $ACR_NAME \
    --image omp/${service}:latest \
    ./src/${service}
done

echo "✅ All images built and pushed to ACR"
```

### Deploy Container Apps

```bash
#!/bin/bash

RESOURCE_GROUP="omp-dev-rg"
ACR_NAME="<from-outputs>"
CAE_NAME="<from-outputs>"
ACR_SERVER="${ACR_NAME}.azurecr.io"

# Get ACR credentials
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

# Deploy services
services=(
  "api-gateway:8000"
  "order-service:8001"
  "inventory-service:8002"
  "payment-service:8003"
  "notification-service:8004"
  "analytics-service:8005"
)

for service_port in "${services[@]}"; do
  IFS=':' read -r service port <<< "$service_port"
  
  az containerapp create \
    --name omp-${service}-dev \
    --resource-group $RESOURCE_GROUP \
    --environment $CAE_NAME \
    --registry-server $ACR_SERVER \
    --registry-username $ACR_USER \
    --registry-password $ACR_PASSWORD \
    --image $ACR_SERVER/omp/${service}:latest \
    --target-port $port \
    --cpu 0.5 \
    --memory 1Gi \
    --env-vars SERVICE_NAME=$service ENVIRONMENT=dev \
    --min-replicas 1 \
    --max-replicas 2 \
    $([ "$service" = "api-gateway" ] && echo "--ingress external" || echo "--ingress internal")
done

echo "✅ All services deployed to Container Apps"
```

### Verify Deployment

```bash
#!/bin/bash

# Get API Gateway FQDN
API_GATEWAY_FQDN=$(az containerapp show \
  --name omp-api-gateway-dev \
  --resource-group omp-dev-rg \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo "🌐 API Gateway available at: https://$API_GATEWAY_FQDN"

# Health checks
echo ""
echo "🏥 Checking service health..."
curl -s https://$API_GATEWAY_FQDN/health | jq .

# Generate auth token
echo ""
echo "🔑 Generating auth token..."
TOKEN=$(curl -s -X POST https://$API_GATEWAY_FQDN/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo-user"}' | jq -r '.access_token')

echo "Token: $TOKEN"

# Test order creation
echo ""
echo "📦 Testing order creation..."
curl -s -X POST https://$API_GATEWAY_FQDN/api/v1/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "test-customer",
    "items": [
      {"sku": "SKU-001", "quantity": 2, "unit_price": 50.00},
      {"sku": "SKU-002", "quantity": 1, "unit_price": 100.00}
    ],
    "total_amount": 200.00
  }' | jq .

echo ""
echo "✅ Deployment verified!"
```

## 🔄 Upgrade & Scale Operations

### Scale Horizontally (Add Replicas)

```bash
# Increase max replicas for handling more load
az containerapp update \
  --name omp-order-service-dev \
  --resource-group omp-dev-rg \
  --min-replicas 2 \
  --max-replicas 5
```

### Use Zero-Downtime Deployment

```bash
# Container Apps automatically handles traffic shifting
# Update image - no manual intervention needed
az containerapp update \
  --name omp-api-gateway-dev \
  --resource-group omp-dev-rg \
  --image $ACR_SERVER/omp/api-gateway:v2.0
```

### Update Secrets

```bash
# Add new secret to Key Vault
az keyvault secret set \
  --vault-name omp-kv-dev-eastus-*** \
  --name new-api-key \
  --value "secret-value"

# Services automatically pick up via Managed Identity
# Force service refresh if needed:
az containerapp update \
  --name omp-order-service-dev \
  --resource-group omp-dev-rg \
  --force-update

# Verify secret access
az keyvault secret show \
  --vault-name omp-kv-dev-eastus-*** \
  --name new-api-key
```

## 📊 Monitoring Post-Deployment

### Access Application Insights Dashboard

```bash
# Get App Insights connection string
APP_INSIGHTS=$(jq -r '.appInsightsConnectionString.value' deployment-outputs.json)
echo "App Insights: $APP_INSIGHTS"

# Open in portal
RESOURCE_GROUP_ID=$(az group show --name omp-dev-rg --query id -o tsv)
APP_INSIGHTS_NAME=$(az resource list --resource-group omp-dev-rg --resource-type "microsoft.insights/components" --query "[0].name" -o tsv)

echo "📊 Open dashboard: https://portal.azure.com#@/resource${RESOURCE_GROUP_ID}/providers/microsoft.insights/components/${APP_INSIGHTS_NAME}/overview"
```

### View Real-Time Metrics

```bash
# Orders created per minute
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query \
  'AppTraces
   | where Message contains "Order created"
   | summarize Orders = count() by bin(TimeGenerated, 1m)
   | render timechart'

# Error rate by service
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query \
  'AppTraces
   | where SeverityLevel >= 2
   | summarize Errors = count() by Cloud_RoleName
   | render barchart'
```

## 🧹 Cleanup

### Remove All Resources

```bash
# This deletes everything - use with caution!
az group delete \
  --name omp-dev-rg \
  --yes \
  --no-wait

echo "Deletion in progress. Verify in portal when complete."
```

### Partial Cleanup (Keep data, delete compute)

```bash
# Delete Container Apps only (keeps data/databases)
az containerapp delete --name omp-api-gateway-dev --resource-group omp-dev-rg --yes
az containerapp delete --name omp-order-service-dev --resource-group omp-dev-rg --yes
# ... repeat for other services

# Cost will be reduced but data preserved for future deployment
```

## 🆕 Deploy to Production

**Use same commands with prod parameters:**

```bash
# Set prod environment
ENVIRONMENT="prod"
RESOURCE_GROUP="omp-prod-rg"
LOCATION="eastus"  # or use different region

# Deploy
az group create --name $RESOURCE_GROUP --location $LOCATION

az deployment group create \
  --name omp-infrastructure \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/params/prod.bicepparam

# Continue with image build and container app deployment
# (Use prod image tags and credentials)
```

## 🐛 Troubleshooting Deployment

### Deployment Failed: Quota Exceeded

```bash
# Check current usage
az vm usage list --location eastus

# Request quota increase
# Submit support request in Azure Portal > Help + Support
```

### Container App Won't Start

```bash
# Check logs
az containerapp logs show \
  --name omp-order-service-dev \
  --resource-group omp-dev-rg \
  --follow

# Common issues:
# - Image not found: Verify ACR image exists
# - Memory/CPU exceeded: Adjust container resources
# - Environment variables missing: Check bicep params
```

### Services Can't Communicate

```bash
# Check private endpoints
az network private-endpoint list \
  --resource-group omp-dev-rg

# Check NSG rules
az network nsg rule list \
  --nsg-name compute-nsg \
  --resource-group omp-dev-rg

# Test connectivity
# From Container App terminal: curl http://order-service:8001/health
```

---

**Deployment Complete!** 🎉

Your OrderManagement Platform is now running in Azure.

- **API Gateway**: $(Get in portal)
- **Monitoring**: Check Application Insights
- **Logs**: Query Log Analytics Workspace
- **Costs**: Review Resource Groups > Costs
