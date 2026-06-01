# Icon Sources for Draw.io Diagrams

This file documents where to fetch icons for diagrams in this workspace — including
the pattern already in use, sources for missing icons, and per-diagram checklists.

---

## 1. Icon Sources Overview

### 1.1 Draw.io MCP Server — Built-in Azure Shape Library

The `drawio-mcp-server` ships a curated Azure icon library sourced from
[dwarfered/azure-architecture-icons-for-drawio](https://github.com/dwarfered/azure-architecture-icons-for-drawio).

Use the `search-shapes` MCP tool to discover exact shape names before calling `add-cells`:

```json
{ "queries": ["Container Apps", "AI Foundry", "AI Search", "Cosmos DB", "Key Vaults"] }
```

Icons resolve automatically when you pass `shape_name` to `add-cells` — no URL needed.
This is the **recommended approach** when working with the Draw.io MCP agent.

---

### 1.2 Microsoft Azure Architecture Icons CDN (already used in this workspace)

**Base URL pattern:**
```
https://learn.microsoft.com/en-us/azure/architecture/media/icons/{Category}/{service-name}.svg
```

This pattern is active in `azure-eventgrid-cv.drawio` and `fabric-multi-layer-architecture.drawio`.

Used in Draw.io cells as:
```xml
style="shape=image;image={URL};imageWidth=80;imageHeight=80;verticalLabelPosition=bottom;labelPosition=center;rounded=1;"
```

**Known working categories and service filenames:**

| Category            | Service                    | Filename                          |
|---------------------|----------------------------|-----------------------------------|
| `AI`                | Cognitive Services         | `cognitive-services.svg`          |
| `Compute`           | Azure Functions            | `azure-functions.svg`             |
| `Compute`           | Azure Container Apps       | `azure-container-apps.svg`        |
| `Databases`         | Cosmos DB                  | `cosmos-db.svg`                   |
| `Governance`        | Microsoft Purview          | `microsoft-purview.svg`           |
| `Identity-Access`   | Azure Active Directory     | `azure-active-directory.svg`      |
| `Integration`       | Event Grid                 | `event-grid.svg`                  |
| `Monitoring`        | Azure Monitor              | `azure-monitor.svg`               |
| `Security`          | Azure Key Vault            | `key-vault.svg`                   |
| `Security`          | Microsoft Sentinel         | `microsoft-sentinel.svg`          |
| `Storage`           | Azure Storage (Blob)       | `azure-storage.svg`               |
| `Storage`           | Azure Data Lake (ADLS Gen2)| `azure-data-lake.svg`             |

**Full icon catalog:** https://learn.microsoft.com/en-us/azure/architecture/icons/

**Bulk download (ZIP):** https://aka.ms/azureicons

---

### 1.3 Third-Party Service Logos (used in fabric-multi-layer-architecture.drawio)

| Service     | Source                                                                             |
|-------------|------------------------------------------------------------------------------------|
| Snowflake   | `https://upload.wikimedia.org/wikipedia/commons/7/7c/Snowflake_Logo.svg`          |
| Power BI    | `https://upload.wikimedia.org/wikipedia/commons/c/cf/Power_BI_logo.svg`           |

For production diagrams, prefer official brand assets:
- **Snowflake brand assets:** https://www.snowflake.com/brand/
- **Microsoft brand assets (Power BI, Fabric):** https://microsoft.com/en-us/microsoft-brand-toolkit

---

### 1.4 Microsoft Fabric Icons

Microsoft Fabric icons are not yet fully available on the standard Azure Architecture Icons CDN.
Use the following sources:

| Service              | Recommended URL / Source                                                                                      |
|----------------------|---------------------------------------------------------------------------------------------------------------|
| Microsoft Fabric     | `https://learn.microsoft.com/en-us/azure/architecture/media/icons/Analytics/microsoft-fabric.svg`            |
| Fabric Workspace     | Use the Fabric icon above with a container/group in Draw.io                                                   |
| Power BI (in Fabric) | `https://upload.wikimedia.org/wikipedia/commons/c/cf/Power_BI_logo.svg`                                      |
| OneLake              | `https://learn.microsoft.com/en-us/azure/architecture/media/icons/Storage/azure-data-lake.svg` (substitute) |

---

## 0. ⚠️ REQUIREMENT: Azure Icons in All New Diagrams

**All architecture diagrams generated in this project MUST use Azure icons, not generic rectangles.**

When generating new diagrams with the `brd-to-architecture-diagram` agent or `project-orchestrator`:

1. **Call `search-shapes`** with all Azure service names (e.g., `"Container Apps"`, `"Cosmos DB"`, `"Key Vault"`).
2. **Use returned `shape_name` values** in `add-cells` for every Azure service vertex.
3. **Reject generic rectangles**: Do NOT pass vertices with `style: "rounded=1;whiteSpace=wrap;"` for Azure services.
4. **Result**: Every Azure component appears with its official icon, not a colored box.

**Examples of correct usage:**
- `{ "shape_name": "Container Apps", "text": "API Layer", "x": 200, "y": 100 }`
- `{ "shape_name": "Cosmos DB", "text": "Document Store", "x": 500, "y": 100 }`
- `{ "shape_name": "Key Vault", "text": "Secrets", "x": 800, "y": 100 }`

**Examples of INCORRECT usage (do not do this):**
- `{ "text": "API Layer", "style": "rounded=1;fillColor=...", "x": 200, "y": 100 }` ❌
- Values containing `rounded=1;whiteSpace=wrap` ❌

See sections [1.1 (Draw.io MCP) and 1.2 (CDN)](#11-drawio-mcp-server--built-in-azure-shape-library) for shape name references.

---



### 2.1 `azure-ai-foundry-architecture.drawio` — All shapes use plain rectangles

Every service in this diagram currently uses a colored rectangle (`rounded=1; fillColor=...`).
The following icons need to be added:

| Cell ID    | Label (current)       | Recommended Icon Source / Shape Name                                                                                           |
|------------|-----------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `agent`    | Agent Service         | MCP `search-shapes`: `"Container Apps"` — or CDN: `.../Compute/azure-container-apps.svg`                                      |
| `foundry`  | Azure AI Foundry      | MCP `search-shapes`: `"AI Foundry"` — or CDN: `.../AI/azure-ai-studio.svg`                                                   |
| `search`   | AI Search             | MCP `search-shapes`: `"AI Search"` — or CDN: `.../AI/cognitive-services.svg`                                                  |
| `blob`     | Blob Storage          | MCP `search-shapes`: `"Storage Accounts"` — or CDN: `.../Storage/azure-storage.svg`                                           |
| `cosmos`   | Cosmos DB             | MCP `search-shapes`: `"Azure Cosmos DB"` — or CDN: `.../Databases/cosmos-db.svg`                                              |
| `vault`    | Key Vault             | MCP `search-shapes`: `"Key Vaults"` — or CDN: `.../Security/key-vault.svg`                                                    |
| `insights` | App Insights          | MCP `search-shapes`: `"Application Insights"` — or CDN: `.../Monitoring/application-insights.svg`                             |
| `identity` | Managed Identity      | MCP `search-shapes`: `"Managed Identities"` — or CDN: `.../Identity-Access/managed-identities.svg`                            |
| `rbac`     | RBAC                  | CDN: `.../Identity-Access/azure-active-directory.svg` (use as Entra ID/RBAC visual)                                           |
| `policy`   | Azure Policy          | MCP `search-shapes`: `"Policy"` — or CDN: `.../Governance/policy.svg`                                                         |
| `network`  | Network Security      | MCP `search-shapes`: `"Network Security Groups"` — or CDN: `.../Networking/network-security-group.svg`                        |
| `audit`    | Audit Logging         | CDN: `.../Monitoring/azure-monitor.svg` (Audit Logging is surfaced via Monitor/Log Analytics)                                  |

---

### 2.2 `fabric-lakehouse-architecture.drawio` — All shapes use plain rectangles

| Cell ID          | Label (current)             | Recommended Icon Source / Shape Name                                                                              |
|------------------|-----------------------------|-------------------------------------------------------------------------------------------------------------------|
| `adls`           | ADLS Gen2                   | MCP `search-shapes`: `"Data Lake"` — or CDN: `.../Storage/azure-data-lake.svg`                                   |
| `snowflake`      | Snowflake                   | Third-party: `https://upload.wikimedia.org/wikipedia/commons/7/7c/Snowflake_Logo.svg`                            |
| `other-sources`  | External Sources            | CDN: `.../Integration/api-management.svg` (generic API) or use a plain shape                                      |
| `bronze-tables`  | Raw Lakehouse Tables        | MCP `search-shapes`: `"Microsoft Fabric"` — or CDN: `.../Analytics/microsoft-fabric.svg`                         |
| `silver-tables`  | Processed Lakehouse Tables  | MCP `search-shapes`: `"Microsoft Fabric"` — same icon, different label                                            |
| `gold-tables`    | Semantic Model              | MCP `search-shapes`: `"Microsoft Fabric"` — same icon, different label                                            |
| `powerbi`        | Power BI Reports            | Third-party: `https://upload.wikimedia.org/wikipedia/commons/c/cf/Power_BI_logo.svg`                             |
| *(no cell)*      | Microsoft Purview           | MCP `search-shapes`: `"Purview"` — or CDN: `.../Governance/microsoft-purview.svg`                                |
| *(no cell)*      | Azure Monitor               | MCP `search-shapes`: `"Monitor"` — or CDN: `.../Monitoring/azure-monitor.svg`                                    |
| *(no cell)*      | Microsoft Sentinel          | MCP `search-shapes`: `"Sentinel"` — or CDN: `.../Security/microsoft-sentinel.svg`                                |
| *(no cell)*      | Azure AD / Entra ID         | MCP `search-shapes`: `"Entra ID"` — or CDN: `.../Identity-Access/azure-active-directory.svg`                     |
| *(no cell)*      | Azure Key Vault             | MCP `search-shapes`: `"Key Vaults"` — or CDN: `.../Security/key-vault.svg`                                       |
| *(no cell)*      | Private Endpoints / VNet    | MCP `search-shapes`: `"Virtual Networks"` — or CDN: `.../Networking/virtual-networks.svg`                        |

---

## 3. Diagrams Already Using Icons (Reference)

### 3.1 `azure-eventgrid-cv.drawio` ✅

| Cell ID     | Icon URL (MS Docs CDN)                                               |
|-------------|----------------------------------------------------------------------|
| `storage`   | `.../Storage/azure-storage.svg`                                      |
| `eventgrid` | `.../Integration/event-grid.svg`                                     |
| `functions` | `.../Compute/azure-functions.svg`                                    |
| `cv`        | `.../AI/cognitive-services.svg`                                      |
| `cosmos`    | `.../Databases/cosmos-db.svg`                                        |

### 3.2 `fabric-multi-layer-architecture.drawio` ✅

| Cell ID     | Icon URL                                                                             |
|-------------|--------------------------------------------------------------------------------------|
| `adls`      | `.../Storage/azure-data-lake.svg`                                                    |
| `snow`      | `https://upload.wikimedia.org/wikipedia/commons/7/7c/Snowflake_Logo.svg`            |
| `pbi`       | `https://upload.wikimedia.org/wikipedia/commons/c/cf/Power_BI_logo.svg`             |
| `aad`       | `.../Identity-Access/azure-active-directory.svg`                                     |
| `kv`        | `.../Security/key-vault.svg`                                                         |
| `purview`   | `.../Governance/microsoft-purview.svg`                                               |
| `monitor`   | `.../Monitoring/azure-monitor.svg`                                                   |
| `sentinel`  | `.../Security/microsoft-sentinel.svg`                                                |

---

## 4. How to Add an Icon to an Existing Cell

### Option A — Draw.io MCP Agent (recommended)

When using the Draw.io MCP agent, use `set-cell-shape` to swap a plain rectangle for a
proper Azure icon. The agent resolves the shape from the built-in library by shape name.

### Option B — Direct XML Edit (shape=image with CDN URL)

Replace the `style` attribute of the cell with:

```xml
style="shape=image;
       image=https://learn.microsoft.com/en-us/azure/architecture/media/icons/{Category}/{service}.svg;
       imageWidth=80;imageHeight=80;
       verticalLabelPosition=bottom;labelPosition=center;
       rounded=1;fillColor={fill};strokeColor={stroke};html=1;"
```

Keep the existing `value`, `id`, `vertex`, `parent`, and `<mxGeometry>` unchanged.

---

## 5. Useful Links

| Resource                                   | URL                                                                                         |
|--------------------------------------------|---------------------------------------------------------------------------------------------|
| Azure Architecture Icons (browse)          | https://learn.microsoft.com/en-us/azure/architecture/icons/                                |
| Azure Architecture Icons (bulk ZIP)        | https://aka.ms/azureicons                                                                   |
| Draw.io Azure stencils (dwarfered GitHub)  | https://github.com/dwarfered/azure-architecture-icons-for-drawio                           |
| drawio-mcp-server source                   | https://github.com/simonkurtz-MSFT/drawio-mcp-server                                       |
| VS Code Draw.io extension                  | https://github.com/hediet/vscode-drawio                                                     |
| Snowflake brand assets                     | https://www.snowflake.com/brand/                                                             |
| Microsoft brand toolkit                    | https://microsoft.com/en-us/microsoft-brand-toolkit                                         |
