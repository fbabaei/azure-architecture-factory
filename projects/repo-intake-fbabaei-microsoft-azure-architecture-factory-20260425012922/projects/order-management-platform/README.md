# OrderManagement Platform - Comprehensive Project README

<!-- markdownlint-disable -->

## 📋 Project Overview

The **OrderManagement Platform** is a production-ready cloud-native microservices architecture built on Azure. It demonstrates enterprise-grade patterns for order processing, inventory management, payment handling, and analytics.

### Architecture Type
- **Microservices Pattern**: 6 independent FastAPI services
- **Communication**: Synchronous (REST) + Asynchronous (Azure Service Bus)
- **Data Layer**: Cosmos DB (NoSQL) + SQL Database (relational)
- **Deployment**: Azure Container Apps (managed Kubernetes)
- **Monitoring**: Application Insights + Log Analytics

## 🏗️ Project Structure

```
order-management-platform/
├── diagrams/                 # Architecture documentation
│   ├── order-management-platform.drawio  # Visual architecture
│   └── order-management-platform.md      # Component inventory
├── src/                      # Microservices code
│   ├── api-gateway/         # Request routing and rate limiting
│   ├── order-service/       # Order management core
│   ├── inventory-service/   # Stock and reservation management
│   ├── payment-service/     # Payment processing
│   ├── notification-service/# Email/SMS notifications
│   ├── analytics-service/   # Metrics and KPIs
│   └── shared-lib/          # Common utilities, models, telemetry
├── infra/                    # Infrastructure as Code (Bicep)
│   ├── main.bicep           # Orchestrator template
│   ├── modules/             # Modular Bicep templates
│   └── params/              # Environment parameters (dev/test/prod)
├── tests/                    # Test suites
│   ├── unit/               # Unit tests (models, services)
│   ├── integration/        # Integration tests (API contracts)
│   └── load/               # Load testing scenarios
├── docker/                  # Container definitions
│   ├── Dockerfile.service  # Service container template
│   └── docker-compose.yml  # Local development setup
└── docs/                    # Documentation
    ├── requirements.md      # Business requirements
    ├── production-checklist.md  # Production readiness
    └── README.md            # This file
```

## 🚀 Quick Start

### Local Development (Docker Compose)

```bash
# Build and start all services locally
cd docker
docker-compose up -d

# Verify services are running
curl http://localhost:8000/health          # API Gateway
curl http://localhost:8001/health          # Order Service
curl http://localhost:8002/health          # Inventory Service
curl http://localhost:8003/health          # Payment Service
curl http://localhost:8004/health          # Notification Service
curl http://localhost:8005/health          # Analytics Service
```

### Prerequisite Environment Variables

Set these for local development:
```bash
export ENVIRONMENT=dev
export SERVICE_NAME=<service-name>
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=dev-key"
export SERVICE_BUS_NAMESPACE_URL="https://<namespace>.servicebus.windows.net"
export COSMOS_DB_CONNECTION_STRING="AccountEndpoint=..."
export JWT_SECRET="dev-secret-key"
```

### Running Tests Locally

```bash
# Unit tests
cd projects/order-management-platform
python -m pytest tests/unit -v --cov=src --cov-report=term-missing

# Integration tests
python -m pytest tests/integration -v

# All tests with coverage report
python -m pytest tests --cov=src --cov-report=html
```

## 🔧 Microservices Overview

### 1. API Gateway (Port 8000)
- **Role**: Single entry point for all requests
- **Responsibilities**:
  - JWT token validation and authentication
  - Rate limiting (100 requests/minute per user)
  - Request routing to backend services
  - Request/response logging
- **Health Endpoint**: `GET /health` → checks downstream services
- **API Routes**:
  - `POST /auth/token` - Generate auth token for testing
  - `POST /api/v1/orders` → routes to Order Service
  - `GET /api/v1/inventory/{sku}` → routes to Inventory Service
  - `GET /api/v1/analytics/metrics` → routes to Analytics Service

### 2. Order Service (Port 8001)
- **Role**: Core order lifecycle management
- **Responsibilities**:
  - Create, read, update, list orders
  - Order validation and status tracking
  - Inventory synchronization (calls Inventory Service)
  - Event publishing (OrderCreated, OrderCancelled)
- **Database**: Azure Cosmos DB (orders collection)
- **Key Endpoints**:
  - `POST /api/v1/orders` - Create order
  - `GET /api/v1/orders/{order_id}` - Get order by ID
  - `GET /api/v1/orders?skip=0&limit=10` - List orders

###  Order Service (Port 8001) - continued
- **Event Publishing**: Publishes OrderCreated event on order creation
- **Dependencies**: Inventory Service (synchronous calls)

### 3. Inventory Service (Port 8002)
- **Role**: Stock and reservation management
- **Responsibilities**:
  - Check stock availability
  - Reserve inventory for orders
  - Release reservations on cancellation
  - Backorder tracking
- **Database**: Azure SQL Database (inventory schema)
- **Key Endpoints**:
  - `GET /api/v1/inventory/{sku}/available` - Check stock
  - `POST /api/v1/inventory/{sku}/reserve` - Reserve units
  - `POST /api/v1/inventory/{sku}/release` - Release reservation

### 4. Payment Service (Port 8003)
- **Role**: Payment processing and settlement
- **Responsibilities**:
  - Process payments for orders
  - Handle refunds
  - Maintain payment ledger
  - Integrate with external payment gateways
- **Database**: Azure Cosmos DB (payments collection)
- **Key Endpoints**:
  - `POST /api/v1/payments` - Process payment
  - `GET /api/v1/payments/{payment_id}` - Get payment details
  - `POST /api/v1/payments/{payment_id}/refund` - Issue refund

### 5. Notification Service (Port 8004)
- **Role**: Customer communications
- **Responsibilities**:
  - Send email order confirmations
  - Send SMS status updates
  - Async notification delivery (via Service Bus)
  - Delivery status tracking
- **Database**: Azure Cosmos DB (notifications collection, audit log)
- **Subscriptions**: OrderCreated, PaymentProcessed, InventoryReserved events
- **Key Endpoints**:
  - `POST /api/v1/notifications` - Send notification
  - `GET /api/v1/notifications/{notification_id}/status` - Check status

### 6. Analytics Service (Port 8005)
- **Role**: Business metrics and insights
- **Responsibilities**:
  - Aggregate order metrics
  - Calculate KPIs (payment success rate, order value, etc.)
  - Generate dashboards
  - Trend analysis
- **Database**: Azure Cosmos DB (analytics collection)
- **Data Sources**: Service Bus events + Application Insights
- **Key Endpoints**:
  - `GET /api/v1/analytics/orders/daily` - Daily metrics
  - `GET /api/v1/analytics/payments/success-rate` - Payment metrics
  - `GET /api/v1/analytics/inventory/turnover` - Inventory metrics

## 🏗️ Azure Infrastructure

### Resource Group
- **Name Pattern**: `{project}-{environment}-rg`
- **Example**: `omp-dev-rg` (Order Management Platform - dev)

### Compute
- **Azure Container Apps**: Manages containerized microservices
- **Azure Container Registry (ACR)**: Stores Docker images
- **Container App Environment**: Network isolation and Dapr integration

### Data & Messaging
- **Azure Cosmos DB**: NoSQL database (orders, payments, notifications, analytics)
- **Azure SQL Database**: Relational database (inventory schema)
- **Azure Service Bus**: Event messaging (6 topics with subscriptions)

### Networking
- **Virtual Network**: `{project}-vnet-{environment}-{location}`
- **Subnets**:
  - `compute-subnet` (10.0.1.0/24) - Container Apps
  - `data-subnet` (10.0.2.0/24) - Private endpoints
  - `gateway-subnet` (10.0.3.0/24) - API Management
- **Private Endpoints**: Cosmos DB, SQL DB, Service Bus, Key Vault, ACR
- **Network Security Groups**: Ingress/egress rules per subnet

### Security
- **Azure Key Vault**: Secures secrets and connection strings
- **Managed Identities**: 6 service identities (one per service)
- **RBAC**: Least-privilege roles per service
- **TLS 1.3**: All in-transit communication encrypted

### Monitoring & Observability
- **Application Insights**: Centralized telemetry
- **Log Analytics Workspace**: Query logs, create dashboards
- **Alerts**: High error rate, availability drops
- **Metrics**: Response time (p50/p95/p99), throughput, error rate

## 📊 Data Model

### Order Service (Cosmos DB)
```json
{
  "order_id": "uuid",
  "customer_id": "string",
  "items": [{"sku": "string", "quantity": int, "unit_price": float}],
  "total_amount": float,
  "status": "CREATED|PENDING_PAYMENT|PAYMENT_CONFIRMED|CANCELLED|...",
  "created_at": "ISO8601",
  "correlation_id": "uuid"
}
```

### Inventory Service (SQL Database)
```sql
CREATE TABLE products (
  product_id UNIQUEIDENTIFIER PRIMARY KEY,
  sku VARCHAR(50) UNIQUE,
  name VARCHAR(255),
  description TEXT
);

CREATE TABLE inventory (
  inventory_id UNIQUEIDENTIFIER PRIMARY KEY,
  product_id UNIQUEIDENTIFIER FK,
  quantity INT,
  reserved_quantity INT,
  location VARCHAR(100),
  last_updated DATETIME
);

CREATE TABLE reservations (
  reservation_id UNIQUEIDENTIFIER PRIMARY KEY,
  inventory_id UNIQUEIDENTIFIER FK,
  order_id VARCHAR(100),
  quantity INT,
  expires_at DATETIME,
  status VARCHAR(50)
);
```

## 🔄 Communication Patterns

### Synchronous (Request-Response)
- **API Gateway** ↔ **Order Service** (REST)
- **Order Service** ↔ **Inventory Service** (REST - sync check for stock)

### Asynchronous (Event-Driven)
- **Order Service** → Azure Service Bus → **Notification** + **Analytics** + **Payment**
- **Payment Service** → Azure Service Bus → **Order Service** + **Notification** + **Analytics**
- **Inventory Service** → Azure Service Bus → **Notification** + **Analytics**

## 🔐 Security & Authorization

### Authentication Flow
1. Client calls API Gateway with credentials
2. Gateway validates JWT token
3. Token includes `sub` (user ID) claim for rate limiting
4. Each service uses Managed Identity for Azure resource access

### RBAC Assignments
- **Order Service MI**: Cosmos DB Contributor, Service Bus Owner
- **Inventory Service MI**: SQL DB Contributor, Service Bus Owner
- **Payment Service MI**: Cosmos DB Contributor, Service Bus Owner
- **Notification Service MI**: Cosmos DB Reader, Service Bus Receives
- **Analytics Service MI**: Cosmos DB Reader, Service Bus Receives, Log Analytics Reader
- **API Gateway MI**: Key Vault Secrets User, Service Bus Sender

### Network Security
- Private endpoints for all PaaS services
- NSG rules restrict cross-subnet traffic
- Outbound internet access only via approved gateways

## 📈 Monitoring & Alerts

### Dashboard Metrics
- **Service Health**: Uptime % for each microservice
- **Request Latency**: p50, p95, p99 percentiles
- **Error Rate**: Failed requests over total
- **Order Throughput**: Orders/second processed
- **Payment Success Rate**: Successful payments %
- **Event Queue Depth**: Service Bus message backlog

### Alert Thresholds
- **High Error Rate**: Alert when errors > 5% for 15 minutes
- **Service Unavailable**: Alert when availability < 99%
- **Slow Requests**: Alert when p99 latency > 5s
- **Dead Letter Queue**: Alert on DLQ messages

## 🚢 Deployment

### Prerequisites
- Azure subscription with appropriate permissions
- Azure CLI installed and authenticated
- Bicep CLI (included with latest Azure CLI)
- Docker for building container images

### Deploy to Dev Environment
```bash
# 1. Build container images
az acr build --registry {acr-name} --image omp/api-gateway:latest ./src/api-gateway
az acr build --registry {acr-name} --image omp/order-service:latest ./src/order-service
# ... repeat for other services

# 2. Deploy infrastructure
az deployment group create \
  --resource-group omp-dev-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/dev.bicepparam

# 3. Deploy Container Apps
az containerapp create \
  --resource-group omp-dev-rg \
  --environment omp-containerappenv-dev-eastus \
  --name omp-api-gateway-dev \
  --image {acr-name}.azurecr.io/omp/api-gateway:latest
# ... repeat for other services
```

### Deploy to Production
```bash
# Same steps with prod parameters
az deployment group create \
  --resource-group omp-prod-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/prod.bicepparam
```

## 📝 Documentation

- **[Architecture Document](diagrams/order-management-platform.md)** - Complete architecture details
- **[Security Guide](docs/SECURITY.md)** - Security policies and audit
- **[Runbook](docs/RUNBOOK.md)** - Operations procedures
- **[Production Checklist](docs/production-checklist.md)** - Pre-deployment validation

## 🧪 Testing

### Test Coverage Goals
- Unit tests: 60%+ coverage of core logic
- Integration tests: All service-to-service APIs
- Contract tests: OpenAPI schema validation
- Load tests: 1000 req/s baseline performance

### Test Execution
```bash
# All tests
pytest tests/ -v --cov=src

# Specific test suite
pytest tests/unit/ -v
pytest tests/integration/ -v

# With HTML coverage report
pytest tests/ --cov=src --cov-report=html
```

## 🐳 Local Development with Docker

```bash
cd docker

# Build all service images
docker-compose build

# Start all services
docker-compose up -d

# Check service logs
docker-compose logs -f order-service

# Stop services
docker-compose down
```

## 🔍 Troubleshooting

### Service won't start
1. Check logs: `docker-compose logs <service-name>`
2. Verify environment variables are set
3. Check port conflicts: `netstat -an | grep LISTEN`

### Connection refused errors
1. Ensure all services are running: `docker-compose ps`
2. Check service URLs in environment
3. Verify network connectivity: `docker network inspect order-management-network`

### Slow requests
1. Check Application Insights for dependency latency
2. Review database query performance
3. Check Service Bus queue depth

## 📞 Support & Contributing

- **Issues**: Log issues with reproduction steps
- **Questions**: Check documentation or raise discussion
- **Contributing**: Submit PRs with test coverage

## 📄 License

Copyright © 2026 OrderManagement Platform. All rights reserved.

---

**Last Updated**: March 23, 2026  
**Version**: 1.0.0  
**Status**: Production Ready
