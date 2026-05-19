# Requirements - Storage Self-Service Provisioning

## Functional Requirements

1. Users can submit storage provisioning requests using a web interface.
2. Requests must be authenticated using Microsoft Entra ID.
3. Provisioning workflow creates and configures Azure Storage resources.
4. Platform emits lifecycle events for each provisioning stage.
5. Platform stores request state and audit events.
6. Platform applies governance and classification workflow.
7. Platform exposes request status and history.

## Non-Functional Requirements

- Availability: 99.9%+
- Security: no embedded secrets; managed identity and Key Vault usage
- Latency: API request acknowledgment under 3 seconds
- Observability: logs, metrics, and alerts for all provisioning workflows
- Compliance: traceable request-to-resource mapping

## Access Control

- Authentication: Microsoft Entra ID
- Authorization: role-based access for requesters, approvers, operators
- Resource access: least privilege with managed identities

## Governance

- Data asset registration and lineage in Microsoft Purview
- Standardized tagging and naming conventions
- Policy checks prior to provisioning completion
