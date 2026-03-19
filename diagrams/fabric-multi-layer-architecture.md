# Microsoft Fabric — Bronze / Silver / Gold Architecture

```mermaid
flowchart LR
  subgraph Sources
    ADLS[ADLS Gen2 (data lake) - Shortcuts]
    SF[Snowflake (mirrored)]
  end

  subgraph FabricWorkspaces
    direction TB
    Bronze[Fabric Workspace - Bronze]
    Silver[Fabric Workspace - Silver]
    Gold[Fabric Workspace - Gold]
  end

  subgraph Analytics
    PBI[Power BI Engine in Fabric]
  end

  ADLS -->|Shortcut access / OneLake pointer| Bronze
  SF -->|Mirror / replication| Bronze
  Bronze -->|Curate / clean / delta| Silver
  Silver -->|Enrich / business models| Gold
  Gold -->|Semantic models / datasets| PBI
  SF -->|Option: external analytics| PBI

  %% Supporting services
  subgraph IdentityAndSecurity
    AAD[Azure AD]
    KV[Azure Key Vault]
    NET[Private Endpoints & VNet]
  end

  subgraph GovernanceMonitoring
    Purview[Microsoft Purview]
    Monitor[Azure Monitor / Log Analytics]
    Sentinel[Microsoft Sentinel]
  end

  Bronze --- Purview
  Silver --- Purview
  Gold --- Purview
  Bronze --- Monitor
  Silver --- Monitor
  Gold --- Monitor
  Purview ---|Lineage & Catalog| PBI
  AAD ---|Auth & RBAC| Bronze
  AAD ---|Auth & RBAC| Silver
  AAD ---|Auth & RBAC| Gold
  KV ---|CMK & secrets| Bronze
  KV ---|CMK & secrets| Silver
  KV ---|CMK & secrets| Gold
  NET ---|Secure Data Plane| ADLS
  NET ---|Secure Connectivity| SF
  Monitor --- Sentinel
```

**Overview**
- Three Fabric workspaces (Bronze, Silver, Gold) implement the medallion pattern inside Fabric.
- Source data: ADLS Gen2 accessed via shortcuts (OneLake pointers) and mirrored data stored in Snowflake for cross-system analytics and failover.
- Bronze: raw ingestion and delta landing (scoped workspace, limited access).
- Silver: cleaning, standardization, and conformed schemas.
- Gold: curated, business-ready datasets and semantic models used by the Power BI engine in Fabric for reporting.

**Monitoring**
- Export Fabric diagnostics and workspace logs to `Azure Monitor` / `Log Analytics` for metrics, query diagnostics, and usage patterns.
- Configure alerts for failed ingestions, latency, and ETL job errors; forward critical alerts to `Microsoft Sentinel` for investigation and SOAR playbooks.
- Track Power BI usage and performance via Fabric usage telemetry and Log Analytics, and surface expensive queries.

**Governance**
- Use `Microsoft Purview` for automated scanning, classification, cataloging, and end-to-end lineage across ADLS, Fabric workspaces, and Snowflake mirrors.
- Define data access policies and row-level security in Purview + Fabric workspaces; map Purview policies to workspace RBAC.
- Maintain a data catalog with owners, SLA, sensitivity labels, and retention tags for each dataset in Bronze/Silver/Gold.

**Security**
- Authentication & Authorization: Enforce `Azure AD` with Conditional Access, MFA, and Privileged Identity Management for admin roles.
- Network: Use `Private Endpoints`/VNet injection for Fabric compute and ADLS; restrict public access to Snowflake with network policies or PrivateLink.
- Encryption: Use Customer-Managed Keys (CMK) in `Azure Key Vault` for encryption at rest; TLS for data in transit.
- Least Privilege: Apply RBAC, service principals, and managed identities for pipelines and Fabric compute.
- Data protection: Apply DLP and sensitivity labels (Purview) and enforce them in Fabric and downstream reports.

**Operational / Deployment Prerequisites**
- Provision one Fabric workspace per medallion (bronze/silver/gold) with separate compute and capacity planning per workload.
- Ensure ADLS Gen2 container ACLs and POSIX permissions are in place; create OneLake shortcuts to data paths.
- Set up Snowflake replication or connector to mirror datasets and configure network/access controls.
- Configure Purview scanning for ADLS and Snowflake; enable lineage collection from Fabric.
- Configure diagnostic settings for Fabric workspaces and route to Log Analytics and a storage account for long-term retention.
- Establish CI/CD for Fabric artifacts and Power BI semantic models (workspace lifecycle management).

**Notes / Recommendations**
- Treat Bronze as low-trust: limited access, short retention, and schema-on-read; promote only validated datasets to Silver/Gold.
- Snapshot critical datasets and retention policies in both ADLS and Snowflake to support recovery and historical reporting.
- Automate cost and query monitoring to detect runaway compute in Gold (Power BI engine) and optimize models (aggregations).

---

File generated: diagrams/fabric-multi-layer-architecture.md
