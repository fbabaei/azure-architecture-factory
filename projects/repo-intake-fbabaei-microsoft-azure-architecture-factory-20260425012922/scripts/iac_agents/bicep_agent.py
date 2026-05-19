"""Azure Bicep IaC specialist.

DEFAULT IaC agent — matches the pre-refactor behaviour of
`scripts/local_brd_runner.py::_build_infra_bicep`. Emits a single
`infra/main.bicep` with:
  - Log Analytics workspace (if observability enabled)
  - Application Insights (if observability enabled)
  - Optional action group for alert email routing
  - NSG + VNet with app subnet (if network_tier != 'public')
  - Extra private-endpoint subnet (if network_tier == 'private')
"""
from __future__ import annotations

from pathlib import Path

from .base import IacAgent, IacEmitContext, IacEmitResult


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _build_main_bicep(enable_observability: bool, network_tier: str) -> str:
    enable_obs_default = "true" if enable_observability else "false"

    params = (
        "targetScope = 'resourceGroup'\n\n"
        "@description('Deployment location')\n"
        "param location string = resourceGroup().location\n\n"
        "@description('Environment name')\n"
        "param environment string = 'dev'\n\n"
        "@description('Logical workload name used in generated resource names')\n"
        "param workloadName string = 'starter-workload'\n\n"
        "@description('Whether the starter should include monitoring and observability resources')\n"
        f"param enableObservability bool = {enable_obs_default}\n\n"
        "@description('Optional operations email for alert notifications. Leave empty to skip email actions.')\n"
        "param operationsEmail string = ''\n"
    )

    if network_tier == "vnet-integrated":
        params += (
            "\n@description('Address prefix for the virtual network')\n"
            "param vnetAddressPrefix string = '10.0.0.0/16'\n\n"
            "@description('Address prefix for the application subnet')\n"
            "param appSubnetPrefix string = '10.0.0.0/24'\n"
        )
    elif network_tier == "private":
        params += (
            "\n@description('Address prefix for the virtual network')\n"
            "param vnetAddressPrefix string = '10.0.0.0/16'\n\n"
            "@description('Address prefix for the application subnet')\n"
            "param appSubnetPrefix string = '10.0.0.0/24'\n\n"
            "@description('Address prefix for the private endpoint subnet')\n"
            "param peSubnetPrefix string = '10.0.1.0/24'\n"
        )

    base = params + "\n\nvar resourceBaseName = toLower(replace('${workloadName}-${environment}', '_', '-'))\n"

    if network_tier in ("vnet-integrated", "private"):
        subnets = (
            "      {\n"
            "        name: 'app-subnet'\n"
            "        properties: {\n"
            "          addressPrefix: appSubnetPrefix\n"
            "          networkSecurityGroup: { id: nsg.id }\n"
            "          delegations: [\n"
            "            {\n"
            "              name: 'app-env-delegation'\n"
            "              properties: { serviceName: 'Microsoft.App/environments' }\n"
            "            }\n"
            "          ]\n"
            "        }\n"
            "      }\n"
        )
        if network_tier == "private":
            subnets += (
                "      {\n"
                "        name: 'pe-subnet'\n"
                "        properties: {\n"
                "          addressPrefix: peSubnetPrefix\n"
                "          privateEndpointNetworkPolicies: 'Disabled'\n"
                "        }\n"
                "      }\n"
            )

        base += (
            "\nresource nsg 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {\n"
            "  name: '${resourceBaseName}-nsg'\n"
            "  location: location\n"
            "  properties: {\n"
            "    securityRules: [\n"
            "      {\n"
            "        name: 'deny-inbound-default'\n"
            "        properties: {\n"
            "          priority: 4000\n"
            "          direction: 'Inbound'\n"
            "          access: 'Deny'\n"
            "          protocol: '*'\n"
            "          sourcePortRange: '*'\n"
            "          destinationPortRange: '*'\n"
            "          sourceAddressPrefix: '*'\n"
            "          destinationAddressPrefix: '*'\n"
            "        }\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "}\n"
            "\nresource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {\n"
            "  name: '${resourceBaseName}-vnet'\n"
            "  location: location\n"
            "  properties: {\n"
            "    addressSpace: { addressPrefixes: [ vnetAddressPrefix ] }\n"
            f"    subnets: [\n{subnets}"
            "    ]\n"
            "  }\n"
            "  dependsOn: [ nsg ]\n"
            "}\n"
        )

    base += (
        "\nresource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = if (enableObservability) {\n"
        "  name: '${resourceBaseName}-law'\n"
        "  location: location\n"
        "  properties: {\n"
        "    retentionInDays: 30\n"
        "    features: {\n"
        "      enableLogAccessUsingOnlyResourcePermissions: true\n"
        "    }\n"
        "  }\n"
        "  sku: {\n"
        "    name: 'PerGB2018'\n"
        "  }\n"
        "}\n\n"
        "resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = if (enableObservability) {\n"
        "  name: '${resourceBaseName}-appi'\n"
        "  location: location\n"
        "  kind: 'web'\n"
        "  properties: {\n"
        "    Application_Type: 'web'\n"
        "    WorkspaceResourceId: logAnalyticsWorkspace.id\n"
        "    IngestionMode: 'LogAnalytics'\n"
        "  }\n"
        "}\n\n"
        "resource operationsActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enableObservability && !empty(operationsEmail)) {\n"
        "  name: '${resourceBaseName}-opsag'\n"
        "  location: 'global'\n"
        "  properties: {\n"
        "    enabled: true\n"
        "    groupShortName: 'opsalert'\n"
        "    emailReceivers: [\n"
        "      {\n"
        "        name: 'operations-team'\n"
        "        emailAddress: operationsEmail\n"
        "        useCommonAlertSchema: true\n"
        "      }\n"
        "    ]\n"
        "  }\n"
        "}\n"
        "\noutput deploymentHint string = 'Replace this starter Bicep file with workload-specific Azure resources.'\n"
        "output locationUsed string = location\n"
        "output environmentName string = environment\n"
        "output observabilityEnabled bool = enableObservability\n"
        "output logAnalyticsWorkspaceName string = enableObservability ? logAnalyticsWorkspace.name : 'not-enabled'\n"
        "output appInsightsName string = enableObservability ? applicationInsights.name : 'not-enabled'\n"
        "output appInsightsConnectionString string = enableObservability ? applicationInsights.properties.ConnectionString : ''\n"
        "output actionGroupName string = (enableObservability && !empty(operationsEmail)) ? operationsActionGroup.name : 'not-configured'\n"
    )

    if network_tier in ("vnet-integrated", "private"):
        base += "output vnetName string = vnet.name\n"
        base += "output appSubnetId string = vnet.properties.subnets[0].id\n"
    if network_tier == "private":
        base += "output peSubnetId string = vnet.properties.subnets[1].id\n"

    return base


class BicepAgent:
    name = "bicep"
    display_name = "Azure Bicep"
    file_extension = ".bicep"

    def emit(self, ctx: IacEmitContext) -> IacEmitResult:
        ctx.infra_dir.mkdir(parents=True, exist_ok=True)
        _write_text(
            ctx.infra_dir / "main.bicep",
            _build_main_bicep(ctx.enable_observability, ctx.network_tier),
        )
        return IacEmitResult(
            files_written=["infra/main.bicep"],
            deploy_bullets=[
                "- Deploy with: `az deployment group create -g <rg> -f infra/main.bicep`",
                "- Validate with: `az deployment group what-if -g <rg> -f infra/main.bicep`",
            ],
        )


AGENT = BicepAgent()
