# Cost Estimation Guide

The Azure Architecture Factory includes built-in cost estimation tools available on every generated project card via the **💰 Cost Tools** button. This guide explains each tool, when to use it, and its limitations.

---

## Overview

| Tool | Tab | Auth Required | When to Use |
|---|---|---|---|
| **Azure Retail Prices API** | 📊 Retail Pricing | None (public) | Quick per-unit pricing at the start of a project |
| **Azure Pricing Calculator** | 🧮 Pricing Calculator | None (public) | Interactive estimate with volume, tier, and region assumptions |
| **ARM What-If CLI** | 🔍 What-If CLI | Azure CLI login | Pre-deploy validation of resource changes on a real subscription |
| **AI Model Cost Calculator** | 🤖 AI Model Costs | None (browser) | Estimate monthly Azure OpenAI token consumption costs |

---

## Tab 1 — Retail Pricing (Azure Retail Prices API)

### What it does
Scans the Bicep files in your generated project, detects recognized Azure resource types, then fetches **live pay-as-you-go USD prices** directly from the [Azure Retail Prices API](https://learn.microsoft.com/azure/cost-management-billing/costs/azure-retail-prices-overview).

Results are displayed in a table showing:
- Resource type (e.g. `Microsoft.App/containerApps`)
- Azure service name
- SKU / plan name
- Unit price in USD
- Unit of measure

### How to use
1. Open a project card and click **💰 Cost Tools**
2. The **Retail Pricing** tab loads automatically
3. Prices are fetched in real time — no login needed

### Limitations
- Shows **pay-as-you-go** (consumption) prices only — does not account for reserved instances, savings plans, or EA discounts
- Only covers resource types the factory recognizes. If a resource type is not in the mapping, it will not appear
- Prices shown are **per unit** (e.g. per vCore-hour, per GB). Actual monthly cost depends on volume

---

## Tab 2 — Pricing Calculator

### What it does
Reads the same detected resource types and generates a deep-link to the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) **pre-populated** with your project's services.

### How to use
1. Click the **🧮 Pricing Calculator** tab
2. Review the list of detected services (shown as tags)
3. Click **🧮 Open Azure Pricing Calculator ↗** — the calculator opens in a new tab with your services pre-selected
4. Adjust quantities, tiers, redundancy, and region to build a realistic monthly estimate
5. Export or save the estimate from within the calculator

### Limitations
- Pre-population relies on product slug mapping; some services may not deep-link perfectly — you may need to adjust selections in the calculator manually
- The calculator does not connect back to the portal — changes are not saved here

---

## Tab 3 — What-If CLI

### What it does
Generates the exact **Azure CLI commands** to run a [deployment What-If analysis](https://learn.microsoft.com/azure/azure-resource-manager/templates/deploy-what-if) against your subscription. What-If shows you exactly which resources would be created, modified, or deleted — before you spend anything.

> **Note:** What-If does not return dollar costs. It validates resource configuration and surfaces breaking changes before deployment.

### Prerequisites
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed locally
- [Bicep CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install) installed (`az bicep install`)
- An Azure subscription with Contributor or Owner rights on the target resource group
- The project ZIP downloaded locally (use the **⬇️ Download ZIP** button on the project card)

### How to use
1. Click the **🔍 What-If CLI** tab
2. Enter your **Subscription ID**, **Resource Group Name**, and **Azure Region**
3. Click **📋 Copy commands** to copy the full command block to your clipboard
4. In a terminal on your local machine, paste and run the commands:
   - `az login` — authenticate to Azure
   - `az account set` — target the correct subscription
   - `az group create` — create the resource group if it does not exist
   - `az bicep build` — compile Bicep to ARM JSON
   - `az deployment group what-if` — preview all resource changes
5. Review the What-If output. Resources are colour-coded: `+ Create`, `~ Modify`, `- Delete`, `= No change`
6. When satisfied, run the actual deployment using the `azure-project-deployer` agent or `az deployment group create`

### Limitations
- What-If requires the Bicep to compile cleanly. If there are missing parameters you will need to provide a parameters file
- What-If accuracy depends on the resource provider. Some providers return incomplete change details

---

## Frequently Asked Questions

**Q: Why are the prices different from my actual Azure bill?**
The Retail Prices API returns list prices. Your actual bill may differ due to reserved capacity, Azure credits, EA/MCA negotiated rates, support plan charges, and egress costs.

**Q: Can I get a total monthly cost estimate in the portal?**
The Retail Pricing tab shows per-unit prices. For a total estimate, use the **Pricing Calculator** tab where you can specify expected volumes and hours.

**Q: Does Cost Tools work for projects that haven't been deployed yet?**
Yes — all three tools are designed for **pre-deployment** use. The Retail Prices API and Pricing Calculator require no subscription. The What-If CLI needs a subscription but does not deploy anything.

**Q: What if my project uses a service not in the pricing table?**
The mapping covers the most common Azure services generated by the factory. For unlisted services, open the Pricing Calculator directly at [azure.microsoft.com/pricing/calculator](https://azure.microsoft.com/pricing/calculator/) and add them manually.

---

## Related Resources

- [Azure Retail Prices API reference](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
- [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
- [ARM What-If documentation](https://learn.microsoft.com/azure/azure-resource-manager/templates/deploy-what-if)
- [Azure Cost Management](https://learn.microsoft.com/azure/cost-management-billing/)
- [azure-project-deployer agent](../projects/INDEX.md)
