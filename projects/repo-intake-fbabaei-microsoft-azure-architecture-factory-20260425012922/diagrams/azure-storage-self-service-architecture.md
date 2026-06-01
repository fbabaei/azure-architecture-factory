# Azure Storage Self-Service Provisioning Architecture

## Overview

This architecture implements a self-service storage provisioning platform through a web service layer, with built-in access control, monitoring, and governance.

## Main Flow

1. User authenticates with Microsoft Entra ID.
2. User submits a provisioning request through the web portal.
3. Provisioning API validates request and persists request state.
4. Workflow engine executes storage provisioning.
5. Event Grid publishes lifecycle events.
6. Storage resources are created and registered for governance.
7. Monitoring captures telemetry and operational signals.

## Azure Services

- **Azure Container Apps**: web portal and API service hosting.
- **Azure Functions**: workflow orchestration and provisioning logic.
- **Azure Storage**: provisioned storage accounts.
- **Azure Data Lake (ADLS Gen2)**: hierarchical namespace/data lake zone.
- **Azure Cosmos DB**: request state, audit trail, and operation metadata.
- **Microsoft Entra ID**: authentication and access control.
- **Azure Key Vault**: secret/certificate management.
- **Azure Monitor**: logs, metrics, alerts, and dashboards.
- **Microsoft Purview**: data governance and catalog integration.
- **Event Grid**: event-driven process notifications.
- **Azure AI Foundry**: optional policy/assistant workflows for request guidance.

## Access Control

- Entra ID for identity and RBAC boundaries.
- Managed identity access to dependent Azure services.
- Role separation for requesters, approvers, and operators.

## Monitoring and Governance

- End-to-end telemetry for request lifecycle.
- Event-driven traceability for each provisioning stage.
- Purview registration for discoverability and governance.
