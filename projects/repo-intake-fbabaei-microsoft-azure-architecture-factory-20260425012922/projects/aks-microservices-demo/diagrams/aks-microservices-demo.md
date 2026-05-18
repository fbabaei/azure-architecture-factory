# AKS Microservices Demo Architecture

## Overview

This architecture captures the AKS-focused sample in this repository.

- Ingress is fronted by Application Gateway with WAF controls.
- Workloads run inside AKS namespaces for API gateway and domain services.
- Data services include PostgreSQL and Redis.
- Platform integrations include ACR, Key Vault, and Azure Monitor through Bicep modules.

## Main Flow

1. Client traffic enters through Application Gateway.
2. Requests are routed to the API gateway workload inside AKS.
3. Domain services process requests and persist state in data services.
4. Telemetry and logs are emitted to monitoring services.
