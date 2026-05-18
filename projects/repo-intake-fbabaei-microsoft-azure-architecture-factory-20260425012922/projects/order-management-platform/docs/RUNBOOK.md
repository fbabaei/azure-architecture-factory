# OrderManagement Platform - Operations Runbook

## 🛠️ Operational Procedures

### Pre-Deployment Checklist

- [ ] Resource group created: `omp-dev-rg` (East US)
- [ ] Bicep templates validated: `bicep lint infra/main.bicep`
- [ ] Required Azure permissions: Contributor on subscription
- [ ] Service principal or user managed identity configured
- [ ] Docker images built and pushed to ACR
- [ ] Container App environment created
- [ ] Network configured (VNet, subnets, private endpoints)
- [ ] Key Vault created and secrets populated
- [ ] Monitoring configured (App Insights, Log Analytics alerts)
- [ ] Database migrations planned

### Deployment Steps

#### 1. Deploy Infrastructure

```bash
# Set variables
RESOURCE_GROUP="omp-dev-rg"
ENVIRONMENT="dev"
LOCATION="eastus"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Deploy infrastructure
az deployment group create \
  --name omp-deployment-$(date +%s) \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/params/dev.bicepparam

# Verify deployment
az deployment group show \
  --name omp-deployment-* \
  --resource-group $RESOURCE_GROUP
```

#### 2. Build and Push Container Images

```bash
# Set ACR name (from deployment output)
ACR_NAME="<acr-name-from-output>"

# Build images
for service in api-gateway order-service inventory-service payment-service notification-service analytics-service; do
  az acr build \
    --registry $ACR_NAME \
    --image omp/${service}:latest \
    ./src/${service}
done

# Verify images
az acr repository list --registry $ACR_NAME
```

#### 3. Deploy Container Apps

```bash
# Get Container App environment
CAE_NAME=$(az containerapp env list \
  --resource-group $RESOURCE_GROUP \
  --query "[0].name" -o tsv)

# Deploy API Gateway
az containerapp create \
  --name omp-api-gateway-dev \
  --resource-group $RESOURCE_GROUP \
  --environment $CAE_NAME \
  --registry-server ${ACR_NAME}.azurecr.io \
  --image ${ACR_NAME}.azurecr.io/omp/api-gateway:latest \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 --memory 1Gi \
  --env-vars \
    SERVICE_NAME=api-gateway \
    ORDER_SERVICE_URL=http://omp-order-service-dev:8001 \
    INVENTORY_SERVICE_URL=http://omp-inventory-service-dev:8002
```

### Post-Deployment Verification

```bash
# Health checks
for port in 8000 8001 8002 8003 8004 8005; do
  curl -s http://localhost:$port/health | jq .
done

# Create test order
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "test-customer",
    "items": [{"sku": "TEST-SKU", "quantity": 1, "unit_price": 99.99}],
    "total_amount": 99.99
  }'

# Check monitoring
az monitor app-insights app-state \
  --app <app-insights-name> \
  --resource-group $RESOURCE_GROUP
```

## 🔄 Common Operations

### Scale Services

**Increase replicas during peak load:**
```bash
az containerapp update \
  --name omp-order-service-dev \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 3 \
  --max-replicas 5
```

**View current scaling:**
```bash
az containerapp show \
  --name omp-order-service-dev \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.scale"
```

### Update Secrets

```bash
# Update JWT secret in Key Vault
az keyvault secret set \
  --vault-name omp-kv-dev \
  --name jwt-secret \
  --value "new-secret-value"

# Services will automatically pick up via Managed Identity
# Restart required for immediate effect:
az containerapp update \
  --name omp-api-gateway-dev \
  --resource-group $RESOURCE_GROUP \
  --force-update
```

### Restart Service

```bash
az containerapp update \
  --name omp-order-service-dev \
  --resource-group $RESOURCE_GROUP \
  --force-update
```

### View Logs

```bash
# Application logs
az containerapp logs show \
  --name omp-order-service-dev \
  --resource-group $RESOURCE_GROUP \
  --follow

# Analytics query for performance
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query \
  'AppTraces | where Cloud_RoleName == "order-service" | order by TimeGenerated desc'
```

## 🚨 Incident Response

### High Error Rate (Alert Triggered)

```bash
# 1. Check affected service status
SERVICE="order-service"
az containerapp show --name omp-${SERVICE}-dev --resource-group $RESOURCE_GROUP

# 2. View recent logs
az containerapp logs show --name omp-${SERVICE}-dev --resource-group $RESOURCE_GROUP --follow

# 3. Query Application Insights
az monitor app-insights metrics show \
  --app omp-appinsights-dev \
  --metric requests/rate

# 4. Check dependencies
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query \
  'AppDependencies | where success == false | summarize count() by Data'

# 5. If needed, restart service
az containerapp update --name omp-${SERVICE}-dev --resource-group $RESOURCE_GROUP --force-update

# 6. Create incident ticket
# Include: timestamp, errors, impact, mitigation, root cause
```

### Service Down (Unresponsive)

```bash
# 1. Check Container App status
az containerapp revision list --name omp-order-service-dev --resource-group $RESOURCE_GROUP

# 2. Check container logs
az containerapp logs show --name omp-order-service-dev --resource-group $RESOURCE_GROUP

# 3. Check resource limits
az containerapp show --name omp-order-service-dev --resource-group $RESOURCE_GROUP | jq '.properties.template'

# 4. Increase resources if needed
az containerapp update \
  --name omp-order-service-dev \
  --resource-group $RESOURCE_GROUP \
  --cpu 1.0 --memory 2Gi

# 5. Restart with force update
az containerapp update \
  --name omp-order-service-dev \
  --resource-group $RESOURCE_GROUP \
  --force-update
```

### Slow Requests (p99 > 5s)

```bash
# 1. Check database performance
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query \
  'AppDependencies | where DependencyType == "cosmosdb" | summarize p99_duration=percentile(DurationMs, 99) by Data'

# 2. Check inter-service latency
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query \
  'AppDependencies | where DependencyType == "http" | summarize count() by Name, p99_duration=percentile(DurationMs, 99)'

# 3. Check Service Bus lag
az servicebus topic subscription show \
  --namespace-name omp-sb-dev-*** \
  --topic-name <topic> \
  --name <subscription>

# 4. If database slow, check query plans
# Connect to Cosmos/SQL and analyze slow queries
```

## 📊 Monitoring Queries

### All Errors in Last Hour
```kusto
AppTraces
| where Timestamp > ago(1h)
| where SeverityLevel >= 2
| summarize count() by Cloud_RoleName, SeverityLevel
| order by count_ desc
```

### Service Response Time (p50/p95/p99)
```kusto
AppRequests
| where Timestamp > ago(1h)
| summarize p50=percentile(DurationMs, 50), p95=percentile(DurationMs, 95), p99=percentile(DurationMs, 99) by Cloud_RoleName
```

### Order Creation Rate
```kusto
AppTraces
| where Timestamp > ago(1d)
| where Message contains "Order created"
| summarize OrderCount=count() by bin(Timestamp, 1h)
| render timechart
```

### Dependency Failures
```kusto
AppDependencies
| where Timestamp > ago(1h)
| where success == false
| summarize FailureCount=count() by DependencyType, Data
```

## 🔄 Backup & Disaster Recovery

### Cosmos DB Backup
```bash
# Automatic backups every 4 hours (kept for 30 days)
# No action needed - enabled by default

# Manual export if needed:
az cosmosdb database export \
  --resource-group $RESOURCE_GROUP \
  --name omp-cosmosdb-dev \
  --dest-account omp-cosmosdb-backup
```

### SQL Database Backup
```bash
# Point-in-time restore (available for 7-35 days, configurable)
az sql db restore \
  --resource-group $RESOURCE_GROUP \
  --server omp-sqldb-dev-*** \
  --name inventory_db \
  --dest-name inventory_db_restored \
  --time "2026-03-23T12:00:00Z"
```

## 📋 Maintenance Schedule

- **Weekly**: Review monitoring dashboards, check backup status
- **Monthly**: Test failover scenarios, validate disaster recovery
- **Quarterly**: Dependency updates, security scanning, performance tuning
- **Annually**: Capacity planning, compliance audit, architecture review

---

**Last Updated**: March 23, 2026  
**On-Call Rotation**: [Link to schedule]  
**Escalation**: Please contact platform team
