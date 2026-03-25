# OrderManagement Platform - Architecture & Component Inventory

<!-- markdownlint-disable -->

## Architecture Overview

The OrderManagement Platform implements a cloud-native microservices architecture on Azure with event-driven asynchronous communication, distributed tracing, and enterprise security patterns.

### Deployment Topology
- **Primary Region**: East US (eastus)
- **Secondary Region**: West US (westus) - future DR
- **Orchestration**: Azure Container Apps (managed Kubernetes)
- **API Entry Point**: Azure API Management with rate limiting and authentication
- **Network**: Virtual Network with private endpoints for secured data access

---

## Core Components

### 1. Client Layer

#### Azure API Management (APIM)
- **Role**: API Gateway, rate limiting, authentication, request/response transformation
- **URL**: https://omp-apim-dev-eastus.azure-api.net
- **Features**: JWT validation, request logging, response caching
- **Connected To**: Order Service, Inventory Service, Analytics Service (read-only)

---

### 2. Compute Layer (Azure Container Apps)

#### API Gateway Service
- **Service Name**: api-gateway
- **Port**: 8000
- **Dependencies**: KeyVault (secrets), Application Insights (telemetry)
- **Responsibilities**: JWT validation, request routing, rate limiting enforcement
- **Health Endpoint**: GET /health
- **Key Routes**:
  - POST /api/v1/orders → Order Service
  - GET /api/v1/inventory/{sku} → Inventory Service
  - GET /api/v1/analytics/metrics → Analytics Service

#### Order Service
- **Service Name**: order-service
- **Port**: 8001
- **Database**: Azure Cosmos DB (Orders container)
- **Message Bus**: Azure Service Bus (Topics: OrderCreated, OrderCancelled)
- **Dependencies**: Inventory Service (sync), Payment Service (async)
- **Health Endpoint**: GET /health
- **Key Endpoints**:
  - POST /api/v1/orders (create)
  - GET /api/v1/orders/{id} (retrieve)
  - GET /api/v1/orders (list with pagination)
  - POST /api/v1/orders/{id}/cancel (cancel)

#### Inventory Service
- **Service Name**: inventory-service
- **Port**: 8002
- **Database**: Azure SQL Database (Inventory schema)
- **Message Bus**: Azure Service Bus (Topics: InventoryReserved, InventoryReleased)
- **Dependencies**: Order Service events (subscribe)
- **Health Endpoint**: GET /health
- **Key Endpoints**:
  - GET /api/v1/inventory/{sku}/available (check stock)
  - POST /api/v1/inventory/{sku}/reserve (reserve units)
  - POST /api/v1/inventory/{sku}/release (cancel reservation)

#### Payment Service
- **Service Name**: payment-service
- **Port**: 8003
- **Database**: Azure Cosmos DB (Payments container)
- **Message Bus**: Azure Service Bus (Topics: PaymentProcessed, PaymentFailed, RefundIssued)
- **Dependencies**: Order Service events (subscribe), External payment gateway
- **Health Endpoint**: GET /health
- **Key Endpoints**:
  - POST /api/v1/payments (process)
  - GET /api/v1/payments/{id} (status)
  - POST /api/v1/payments/{id}/refund (refund)

#### Notification Service
- **Service Name**: notification-service
- **Port**: 8004
- **Database**: Azure Cosmos DB (Notifications container, audit log)
- **Message Bus**: Azure Service Bus (Subscriptions to: OrderCreated, OrderCancelled, PaymentProcessed, InventoryReserved)
- **External**: Email service API, SMS gateway API
- **Health Endpoint**: GET /health
- **Key Endpoints**:
  - GET /api/v1/notifications/{id}/status (check delivery status)

#### Analytics Service
- **Service Name**: analytics-service
- **Port**: 8005
- **Database**: Azure Cosmos DB (Analytics container, events aggregation)
- **Message Bus**: Azure Service Bus (Subscriptions to: OrderCreated, PaymentProcessed, InventoryReserved)
- **Log Source**: Application Insights (KQL queries)
- **Health Endpoint**: GET /health
- **Key Endpoints**:
  - GET /api/v1/analytics/orders/daily (daily order metrics)
  - GET /api/v1/analytics/payments/success-rate (payment success rate)
  - GET /api/v1/analytics/inventory/turnover (inventory metrics)

#### Shared Lib
- **Location**: src/shared-lib/
- **Contents**: 
  - Common models (Order, Payment, Notification, AnalyticsEvent)
  - Service Bus event publishers/subscribers
  - Azure SDK initialization and pooling
  - Health check utilities
  - Telemetry instrumentation
  - Retry policies and circuit breaker implementation

---

### 3. Messaging Layer

#### Azure Service Bus
- **Namespace**: omp-sb-dev-eastus
- **Topics & Subscriptions**:
  - **OrderCreated** → subscribed by: Inventory Service, Payment Service, Analytics Service, Notification Service
  - **OrderCancelled** → subscribed by: Inventory Service, Notification Service
  - **PaymentProcessed** → subscribed by: Order Service, Notification Service, Analytics Service
  - **PaymentFailed** → subscribed by: Order Service, Notification Service
  - **InventoryReserved** → subscribed by: Notification Service, Analytics Service
  - **InventoryReleased** → subscribed by: Order Service

- **Dead-Letter Queues**: All subscriptions configured with DLQ for poison message handling

---

### 4. Data Layer

#### Azure Cosmos DB (NoSQL - Multi-region capable)
- **Account**: omp-cosmosdb-dev-eastus
- **Database**: order_management_db
- **Collections**:
  - **orders**: Documents with OrderId as partition key
    - Schema: {orderId, customerId, items[], totalAmount, status, timestamps, correlationId}
  - **payments**: Documents with PaymentId as partition key
    - Schema: {paymentId, orderId, amount, method, status, timestamps, correlationId}
  - **notifications**: Documents with NotificationId as partition key
    - Schema: {notificationId, orderId, type(email|sms), recipient, status, timestamps}
  - **analytics**: Documents with date as partition key
    - Schema: {date, metrics: {ordersCreated, ordersCancelled, paymentsSuccess, inventoryTurns}, timestamps}

- **Features**: TTL policies for old analytics data, global read replicas for compliance

#### Azure SQL Database (Relational)
- **Server**: omp-sqldb-dev-eastus
- **Database**: inventory_db
- **Schema**:
  - **products**: ProductId (PK), Sku (UQ), Name, Description
  - **inventory**: InventoryId (PK), ProductId (FK), Quantity, ReservedQuantity, Location, LastUpdated
  - **reservations**: ReservationId (PK), InventoryId (FK), OrderId, Quantity, ExpiresAt, Status
  - **audit_log**: Timestamp (PK), Action, ResourceId, Details, User

- **Features**: Connection pooling (asyncpg), read replicas for analytics

---

### 5. Security Layer

#### Azure Key Vault
- **Name**: omp-kv-dev-eastus
- **Secrets Stored**:
  - CosmosDB connection string (encrypted)
  - SQL Database connection string (encrypted)
  - Service Bus connection string (encrypted)
  - API Management subscription key
  - External service credentials (payment gateway, email, SMS)
  - JWT signing keys

#### Network Security
- **Virtual Network**: omp-vnet-dev-eastus
- **Subnets**:
  - **compute-subnet**: Container Apps workload
  - **data-subnet**: PaaS services with private endpoints
  - **gateway-subnet**: API Management
- **Network Security Groups**:
  - Inbound: HTTPS (443) from APIM to Container Apps
  - Inbound: Only Azure services to private endpoints
  - Egress: Unrestricted for service communication
- **Private Endpoints**:
  - Cosmos DB: cosmos.database.azure.com/omp-cosmosdb-dev-eastus
  - SQL Database: omp-sqldb-dev-eastus.database.windows.net
  - Service Bus: omp-sb-dev-eastus.servicebus.windows.net
  - Key Vault: omp-kv-dev-eastus.vault.azure.net
  - Container Registry: omp-acr-dev-eastus.azurecr.io

#### Managed Identities & RBAC
- **API Gateway MI**: `api-gateway-mi-dev`
  - Roles: Service Bus Data Sender, Key Vault Secrets User
- **Order Service MI**: `order-service-mi-dev`
  - Roles: Cosmos DB Data Contributor, Service Bus Data Owner, Key Vault Secrets User, Application Insights Component Contributor
- **Inventory Service MI**: `inventory-service-mi-dev`
  - Roles: SQL Database Contributor, Service Bus Data Owner, Key Vault Secrets User, Application Insights Component Contributor
- **Payment Service MI**: `payment-service-mi-dev`
  - Roles: Cosmos DB Data Contributor, Service Bus Data Owner, Key Vault Secrets User, Application Insights Component Contributor
- **Notification Service MI**: `notification-service-mi-dev`
  - Roles: Cosmos DB Data Reader, Service Bus Data Receiver, Key Vault Secrets User, Application Insights Component Contributor
- **Analytics Service MI**: `analytics-service-mi-dev`
  - Roles: Cosmos DB Data Reader, Service Bus Data Receiver, Log Analytics Reader, Key Vault Secrets User, Application Insights Reader

---

### 6. Monitoring & Observability Layer

#### Application Insights
- **Resource**: omp-appinsights-dev-eastus
- **Connected Services**: All 6 microservices via SDKs
- **Instrumentation**:
  - Distributed tracing with W3C Trace Context (correlation IDs)
  - Request/response logging with status codes and durations
  - Exception tracking with stack traces
  - Custom metrics: order volume, payment success rate, service latency
  - Dependencies tracking: Cosmos DB queries, SQL Database connections, Service Bus operations

#### Log Analytics Workspace
- **Resource**: omp-law-dev-eastus
- **Connected Sources**:
  - Application Insights (automatic)
  - Azure Diagnostics from all Azure services
- **Queries**:
  - Service health queries (uptime calculation)
  - Performance queries (p50, p95, p99 latencies)
  - Error analysis queries
  - Business metric queries
- **Retention**: 30 days (configurable)

#### Monitoring Dashboards
- **Service Health Dashboard**: Uptime and availability of all services
- **Performance Dashboard**: Latency distribution (p50/p95/p99), throughput
- **Business Metrics Dashboard**: Orders created/cancelled, payment success rate, inventory metrics
- **Security Dashboard**: RBAC access events, Key Vault access, audit log summary
- **Event Bus Dashboard**: Message queue depth, DLQ messages, consumer lag
- **Database Performance Dashboard**: Query times, connection pool utilization, data growth

---

## Data Flow Patterns

### Synchronous Flow: Create Order
```
Client → APIM (auth) → API Gateway (rate limit) 
  → Order Service (validate) 
  → Inventory Service (reserve stock sync call)
  → Order Service (persist to Cosmos DB)
  → Publishes OrderCreated event
Response: 201 Created with Order ID
```

### Asynchronous Flow: Order to Payment
```
Order Service publishes OrderCreated event
  → Service Bus topic with multiple subscriptions
  → Payment Service subscribes → Processes payment → publishes PaymentProcessed
  → Notification Service subscribes → Sends email confirmation
  → Analytics Service subscribes → Updates metrics
```

### Event-Driven Inventory Check
```
Notification Service subscribes to OrderCreated
  → Retrieves order details
  → Can query Analytics Service for inventory KPIs
  → Personalizes notification with stock info
```

---

## Service Communication Matrix

| Service → | Order | Inventory | Payment | Notification | Analytics |
|-----------|-------|-----------|---------|--------------|-----------|
| **API Gateway** | REST | REST | REST | - | REST |
| **Order Service** | - | REST (sync) | Events | Events | Events |
| **Inventory Service** | Events | - | - | Events | Events |
| **Payment Service** | Events | - | - | Events | Events |
| **Notification** | Events | - | Events | - | - |
| **Analytics** | Events | Events | Events | - | - |

---

## Deployment Architecture

### Container Apps Environment
- **Resource Group**: omp-dev-rg (East US)
- **Container Apps Environment**: omp-containerappenv-dev-eastus
- **Network Profile**: Connected to omp-vnet-dev-eastus
- **Ingress Configuration**:
  - APIM routes traffic to Container Apps
  - Internal traffic between services uses Container Apps DNS
  - External calls use HTTPS with certificate managed by Azure

### Image Registry
- **Azure Container Registry (ACR)**: omp-acr-dev-eastus
- **Image Format**: `omp-acr-dev-eastus.azurecr.io/service-name:latest`
- **Images Built**:
  - order-management-platform/api-gateway:latest
  - order-management-platform/order-service:latest
  - order-management-platform/inventory-service:latest
  - order-management-platform/payment-service:latest
  - order-management-platform/notification-service:latest
  - order-management-platform/analytics-service:latest

---

## Resilience & Fault Tolerance

### Circuit Breaker Pattern
- All cross-service REST calls wrapped with circuit breaker
- Failure threshold: 5 consecutive failed requests
- Fallback: Return 503 Service Unavailable
- Recovery: Exponential backoff retry with jitter

### Retry Policies
- Transient errors (429, 5xx): 3 retries with exponential backoff (0.1s * 2^n)
- Dead-Letter Queues: Failed message processing after 3 retries
- Manual replay from DLQ via admin tools

### Health Checks
- **Frequency**: Every 30 seconds
- **Readiness**: All dependencies reachable (databases, service bus, Key Vault)
- **Liveness**: Process running, memory usage acceptable
- **Graceful Shutdown**: 30-second drain period for in-flight requests

---

## Security Zones

1. **Public Zone**: 
   - Azure API Management endpoint
   - TLS 1.3 encryption mandatory
   - Rate limiting enforced
   - JWT validation required

2. **Application Zone**: 
   - Azure Container Apps running microservices
   - Managed identities for all service authentication
   - Mutual TLS between services (future enhancement)
   - Service Bus with shared access policies

3. **Data Zone**: 
   - Azure Cosmos DB with private endpoints
   - Azure SQL Database with private endpoints
   - Key Vault with private endpoint
   - All communication encrypted in transit and at rest

---

## Component Inventory Summary

| Component | Azure Service | Count | Environment |
|-----------|---------------|-------|-------------|
| Microservices | Container Apps | 6 | dev |
| Managed Identity | Entra ID | 6 | dev |
| API Gateway | APIM | 1 | dev |
| Message Topics | Service Bus | 6 | dev |
| NoSQL Database | Cosmos DB | 3 containers | dev |
| SQL Database | SQL DB | 1 database | dev |
| Secret Storage | Key Vault | 1 | dev |
| Container Images | ACR | 6 | shared |
| Monitoring | App Insights | 1 | dev |
| Log Analytics | LAW | 1 | dev |
| Virtual Network | VNet | 1 | dev |
| Private Endpoints | Azure | 5 | dev |
| NSG Rules | Network | 4 | dev |

---

## Cost Optimization Strategies

1. **Cosmos DB**: Autoscale to manage burst loads, TTL policies to archive old data
2. **SQL Database**: Serverless compute tier scales automatically
3. **Container Apps**: Automatic scaling based on CPU/memory targets
4. **Service Bus**: Shared namespace for all topics (economies of scale)
5. **Log Analytics**: 30-day retention balances cost with compliance
6. **App Insights**: Sampling enabled for high-volume traces (0.5% for non-errors)
