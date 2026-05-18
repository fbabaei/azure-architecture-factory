# OrderManagement Platform - Security & Governance Guide

<!-- markdownlint-disable -->

## 🔒 Security Architecture

The OrderManagement Platform implements multiple layers of security aligned with Azure Well-Architected Framework security pillar.

### Security Layers

#### 1. Authentication & Authorization

**API Gateway Authentication**
- JWT token-based authentication
- Token validation at gateway (no per-service validation overhead)
- Claims include: `sub` (user ID), `iat`, `exp`
- Rate limiting based on user identity

**Service-to-Service Authentication**
- Azure Managed Identities for all services
- No credential storage - uses RBAC + Managed Identity
- Azure SDK automatically handles token acquisition

#### 2. Data Protection

**In Transit**
- TLS 1.3 mandatory for all HTTPS connections
- Service-to-service communication via private endpoints
- Connection pooling with encryption enabled

**Data at Rest**
- Azure Cosmos DB: Encryption with service-managed keys
- Azure SQL Database: Transparent Data Encryption (TDE)
- Azure Key Vault: FIPS 140-2 Level 2 certified storage
- Secrets: Never logged, stored only in Key Vault

#### 3. Network Security

**Virtual Network Design**
```
Internet → API Gateway (Public)
            ↓
         APIM (Rate Limited, Auth)
            ↓
compute-subnet (Container Apps, Private)
   ├── Order Service (with MI)
   ├── Inventory Service (with MI)
   ├── Payment Service (with MI)
   ├── Notification Service (with MI)
   └── Analytics Service (with MI)
            ↓ (Private Endpoints)
data-subnet (Managed Services)
   ├── Cosmos DB
   ├── SQL Database
   ├── Service Bus
   └── Key Vault
```

**Network Security Groups (NSGs)**
- `compute-nsg`: Inbound HTTPS from APIM only
- `data-nsg`: Inbound from private endpoints only
- `gateway-nsg`: Internet facing with rate limiting

**Private Endpoints**
- All PaaS services (Cosmos, SQL, Service Bus, KeyVault, ACR)
- No public IP addresses needed
- Encrypted tunnels to Azure backbone network

#### 4. Identity & Access Management

**Managed Identities**
| Service | Permissions |
|---------|------------|
| API Gateway | Key Vault Secrets User, Service Bus Data Sender |
| Order Service | Cosmos DB Data Contributor, Service Bus Data Owner, KV Secrets User |
| Inventory Service | SQL DB Contributor, Service Bus Data Owner, KV Secrets User |
| Payment Service | Cosmos DB Data Contributor, Service Bus Data Owner, KV Secrets User |
| Notification Service | Cosmos DB Data Reader, Service Bus Data Receiver, KV Secrets User |
| Analytics Service | Cosmos DB Data Reader, Service Bus Data Receiver, Log Analytics Reader, KV Secrets User |

**RBAC Principles**
- Least privilege: Each service has minimal required permissions
- No wildcard roles assigned
- Role assignments scoped to specific resources
- Quarterly access review process

#### 5. Secrets Management

**Key Vault Policies**
- Secrets: Create, Get, List, Delete (for pipelines), Set policies (admins only)
- Keys: Sign, Verify (for JWT), Encrypt, Decrypt
- Certificates: Import, Get, List, Delete

**Secret Rotation**
- Connection strings: Every 90 days
- API keys: Every 60 days
- JWT signing keys: Every 6 months
- Automated rotation via Azure automation (future enhancement)

**Audit Trail**
- All Key Vault access logged to Log Analytics
- Failed access attempts trigger alerts
- Query: `AzureDiagnostics | where ResourceType == "VAULTS"`

#### 6. Application Security

**Input Validation**
- FastAPI Pydantic models enforce schema validation
- SQL queries use parameterized statements (async SQL driver)
- No raw SQL concatenation
- Request size limits enforced

**Error Handling**
- Generic error messages to clients
- Detailed errors logged internally only
- No stack traces exposed in API responses
- Correlation IDs for tracing

**Dependency Security**
- Python dependencies: Pinned versions in requirements.txt
- Annual vulnerability scan: `pip-audit`
- Security updates: Applied within 30 days of patch release

### Security Audit Checklist

#### Infrastructure as Code
✅ Bicep templates validated (bicep linter)
✅ No hardcoded secrets in IaC
✅ Resource naming follows conventions
✅ Tags applied for compliance tracking
✅ Encryption enabled on all storage
✅ Private endpoints configured
✅ NSG rules documented

#### Identity & Secrets
✅ Managed Identities created per service
✅ No service principal passwords stored
✅ Key Vault access policies locked down
✅ Key Vault audit logging enabled
✅ Secret rotation policy documented
✅ No credentials in Docker images
✅ No credentials in Git repositories

#### Network & Access
✅ VNet architecture with subnet isolation
✅ Private endpoints for all data stores
✅ NSG rules restrict access to least privilege
✅ API rate limiting configured
✅ JWT validation at API Gateway
✅ TLS 1.3 enforced
✅ DDoS protection enabled (Azure DDoS Standard)

#### Monitoring & Audit
✅ Application Insights enabled on all services
✅ Diagnostic logging to Log Analytics
✅ Alerts configured for security events
✅ Service health checks working
✅ Correlation IDs tracked
✅ Failed auth attempts logged
✅ Audit trail searchable and retained

#### Code & Container
✅ Code reviewed before merge
✅ Static code analysis run (future: SonarQube)
✅ Container images scanned for vulnerabilities
✅ Docker layers minimized
✅ No root user in containers
✅ Health checks in containers
✅ Read-only file system where possible

### Compliance Considerations

**GDPR**
- Customer data (orders) retention: Configurable TTL in Cosmos DB
- Right to delete: Query API for user orders, cascade delete
- Data portability: Export API (JSON format)
- Privacy impact assessment documented

**PCI DSS** (for payment processing)
- Payment Service isolated from customer data
- No credit card storage (external gateway only)
- Encryption in transit and rest
- Access controls documented

**SOC 2 Type II**
- Change management process (git + reviews)
- Incident response procedures documented
- User access provisioning/deprovisioning automated
- Logical and physical access controls
- Data backup and recovery tested

### Incident Response

**Procedure**
1. **Detect**: Alert triggered by monitoring
2. **Respond**: On-call engineer investigates
3. **Contain**: Isolate affected service/data
4. **Eradicate**: Fix root cause
5. **Recover**: Restore normal operations
6. **Review**: Post-incident review within 24 hours

**Runbooks Available**
- High error rate response
- Service down response
- Slow requests response
- Payment failure response
- Data breach response

### Security Monitoring

**Key Metrics**
- Failed authentication attempts: Alert if > 10 in 5 min
- Key Vault access denied: Alert if > 5 in 10 min
- NSG blocked traffic: Alert if > 100 in 10 min
- Unhealthy service: Alert if down > 2 min
- High latency: Alert if p99 > 5 seconds

**Query Examples**

Failed auth attempts:
```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where OperationName == "VaultGet" and httpStatusCode_d >= 400
| summarize FailedAttempts = count() by CallerIPAddress, bin(TimeGenerated, 5m)
```

Service errors by type:
```kusto
AppTraces
| where Message contains "ERROR"
| summarize ErrorCount = count() by SeverityLevel, Cloud_RoleName
| order by ErrorCount desc
```

## 🔍 Regular Security Reviews

- **Weekly**: Check monitoring dashboards for anomalies
- **Monthly**: Access review, vulnerability scanning
- **Quarterly**: Full security assessment, penetration testing coordination
- **Annually**: Compliance audit, dependency updates

---

**Last Reviewed**: March 23, 2026  
**Next Review**: June 23, 2026
