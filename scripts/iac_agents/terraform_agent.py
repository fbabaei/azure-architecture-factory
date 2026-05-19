"""HashiCorp Terraform IaC specialist.

Emits a multi-file Terraform config matching the Bicep agent's logical
resource shape: Log Analytics, Application Insights, action group, VNet, NSG.
Uses the `azurerm` provider.

Layout:
    infra/providers.tf
    infra/variables.tf
    infra/main.tf
    infra/outputs.tf
    infra/terraform.tfvars.example
"""
from __future__ import annotations

from pathlib import Path

from .base import IacAgent, IacEmitContext, IacEmitResult


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _build_providers() -> str:
    return (
        "terraform {\n"
        "  required_version = \">= 1.6.0\"\n"
        "  required_providers {\n"
        "    azurerm = {\n"
        "      source  = \"hashicorp/azurerm\"\n"
        "      version = \"~> 4.14\"\n"
        "    }\n"
        "  }\n"
        "}\n\n"
        "provider \"azurerm\" {\n"
        "  features {}\n"
        "}\n"
    )


def _build_variables(enable_observability: bool, network_tier: str) -> str:
    enable_obs_default = "true" if enable_observability else "false"
    base = (
        "variable \"resource_group_name\" {\n"
        "  description = \"Existing resource group where resources will be deployed.\"\n"
        "  type        = string\n"
        "}\n\n"
        "variable \"location\" {\n"
        "  description = \"Azure region for all resources.\"\n"
        "  type        = string\n"
        "  default     = \"eastus\"\n"
        "}\n\n"
        "variable \"environment\" {\n"
        "  description = \"Environment name used in resource naming (e.g. dev, test, prod).\"\n"
        "  type        = string\n"
        "  default     = \"dev\"\n"
        "}\n\n"
        "variable \"workload_name\" {\n"
        "  description = \"Logical workload name used in generated resource names.\"\n"
        "  type        = string\n"
        "  default     = \"starter-workload\"\n"
        "}\n\n"
        "variable \"enable_observability\" {\n"
        "  description = \"Whether to provision Log Analytics and Application Insights.\"\n"
        "  type        = bool\n"
        f"  default     = {enable_obs_default}\n"
        "}\n\n"
        "variable \"operations_email\" {\n"
        "  description = \"Optional email for alert notifications. Leave empty to skip the action group.\"\n"
        "  type        = string\n"
        "  default     = \"\"\n"
        "}\n"
    )
    if network_tier in ("vnet-integrated", "private"):
        base += (
            "\nvariable \"vnet_address_prefix\" {\n"
            "  description = \"CIDR for the virtual network.\"\n"
            "  type        = string\n"
            "  default     = \"10.0.0.0/16\"\n"
            "}\n\n"
            "variable \"app_subnet_prefix\" {\n"
            "  description = \"CIDR for the application subnet.\"\n"
            "  type        = string\n"
            "  default     = \"10.0.0.0/24\"\n"
            "}\n"
        )
    if network_tier == "private":
        base += (
            "\nvariable \"pe_subnet_prefix\" {\n"
            "  description = \"CIDR for the private endpoint subnet.\"\n"
            "  type        = string\n"
            "  default     = \"10.0.1.0/24\"\n"
            "}\n"
        )
    return base


def _build_main(enable_observability: bool, network_tier: str) -> str:
    parts: list[str] = []

    parts.append(
        "locals {\n"
        "  resource_base_name = lower(replace(\"${var.workload_name}-${var.environment}\", \"_\", \"-\"))\n"
        "}\n\n"
        "data \"azurerm_resource_group\" \"rg\" {\n"
        "  name = var.resource_group_name\n"
        "}\n"
    )

    if network_tier in ("vnet-integrated", "private"):
        nsg = (
            "\nresource \"azurerm_network_security_group\" \"nsg\" {\n"
            "  name                = \"${local.resource_base_name}-nsg\"\n"
            "  location            = var.location\n"
            "  resource_group_name = data.azurerm_resource_group.rg.name\n\n"
            "  security_rule {\n"
            "    name                       = \"deny-inbound-default\"\n"
            "    priority                   = 4000\n"
            "    direction                  = \"Inbound\"\n"
            "    access                     = \"Deny\"\n"
            "    protocol                   = \"*\"\n"
            "    source_port_range          = \"*\"\n"
            "    destination_port_range     = \"*\"\n"
            "    source_address_prefix      = \"*\"\n"
            "    destination_address_prefix = \"*\"\n"
            "  }\n"
            "}\n"
        )
        vnet = (
            "\nresource \"azurerm_virtual_network\" \"vnet\" {\n"
            "  name                = \"${local.resource_base_name}-vnet\"\n"
            "  location            = var.location\n"
            "  resource_group_name = data.azurerm_resource_group.rg.name\n"
            "  address_space       = [var.vnet_address_prefix]\n"
            "}\n\n"
            "resource \"azurerm_subnet\" \"app\" {\n"
            "  name                 = \"app-subnet\"\n"
            "  resource_group_name  = data.azurerm_resource_group.rg.name\n"
            "  virtual_network_name = azurerm_virtual_network.vnet.name\n"
            "  address_prefixes     = [var.app_subnet_prefix]\n\n"
            "  delegation {\n"
            "    name = \"app-env-delegation\"\n"
            "    service_delegation {\n"
            "      name = \"Microsoft.App/environments\"\n"
            "    }\n"
            "  }\n"
            "}\n\n"
            "resource \"azurerm_subnet_network_security_group_association\" \"app\" {\n"
            "  subnet_id                 = azurerm_subnet.app.id\n"
            "  network_security_group_id = azurerm_network_security_group.nsg.id\n"
            "}\n"
        )
        parts.append(nsg)
        parts.append(vnet)
        if network_tier == "private":
            parts.append(
                "\nresource \"azurerm_subnet\" \"pe\" {\n"
                "  name                                      = \"pe-subnet\"\n"
                "  resource_group_name                       = data.azurerm_resource_group.rg.name\n"
                "  virtual_network_name                      = azurerm_virtual_network.vnet.name\n"
                "  address_prefixes                          = [var.pe_subnet_prefix]\n"
                "  private_endpoint_network_policies         = \"Disabled\"\n"
                "}\n"
            )

    parts.append(
        "\nresource \"azurerm_log_analytics_workspace\" \"law\" {\n"
        "  count               = var.enable_observability ? 1 : 0\n"
        "  name                = \"${local.resource_base_name}-law\"\n"
        "  location            = var.location\n"
        "  resource_group_name = data.azurerm_resource_group.rg.name\n"
        "  sku                 = \"PerGB2018\"\n"
        "  retention_in_days   = 30\n"
        "}\n\n"
        "resource \"azurerm_application_insights\" \"appi\" {\n"
        "  count               = var.enable_observability ? 1 : 0\n"
        "  name                = \"${local.resource_base_name}-appi\"\n"
        "  location            = var.location\n"
        "  resource_group_name = data.azurerm_resource_group.rg.name\n"
        "  workspace_id        = azurerm_log_analytics_workspace.law[0].id\n"
        "  application_type    = \"web\"\n"
        "}\n\n"
        "resource \"azurerm_monitor_action_group\" \"ops\" {\n"
        "  count               = var.enable_observability && var.operations_email != \"\" ? 1 : 0\n"
        "  name                = \"${local.resource_base_name}-opsag\"\n"
        "  resource_group_name = data.azurerm_resource_group.rg.name\n"
        "  short_name          = \"opsalert\"\n\n"
        "  email_receiver {\n"
        "    name                    = \"operations-team\"\n"
        "    email_address           = var.operations_email\n"
        "    use_common_alert_schema = true\n"
        "  }\n"
        "}\n"
    )
    return "".join(parts)


def _build_outputs(enable_observability: bool, network_tier: str) -> str:
    base = (
        "output \"deployment_hint\" {\n"
        "  value = \"Replace these starter Terraform resources with workload-specific Azure resources.\"\n"
        "}\n\n"
        "output \"location_used\" {\n"
        "  value = var.location\n"
        "}\n\n"
        "output \"environment_name\" {\n"
        "  value = var.environment\n"
        "}\n\n"
        "output \"observability_enabled\" {\n"
        "  value = var.enable_observability\n"
        "}\n\n"
        "output \"log_analytics_workspace_name\" {\n"
        "  value = var.enable_observability ? azurerm_log_analytics_workspace.law[0].name : \"not-enabled\"\n"
        "}\n\n"
        "output \"app_insights_name\" {\n"
        "  value = var.enable_observability ? azurerm_application_insights.appi[0].name : \"not-enabled\"\n"
        "}\n\n"
        "output \"app_insights_connection_string\" {\n"
        "  value     = var.enable_observability ? azurerm_application_insights.appi[0].connection_string : \"\"\n"
        "  sensitive = true\n"
        "}\n\n"
        "output \"action_group_name\" {\n"
        "  value = (var.enable_observability && var.operations_email != \"\") ? azurerm_monitor_action_group.ops[0].name : \"not-configured\"\n"
        "}\n"
    )
    if network_tier in ("vnet-integrated", "private"):
        base += (
            "\noutput \"vnet_name\" {\n"
            "  value = azurerm_virtual_network.vnet.name\n"
            "}\n\n"
            "output \"app_subnet_id\" {\n"
            "  value = azurerm_subnet.app.id\n"
            "}\n"
        )
    if network_tier == "private":
        base += (
            "\noutput \"pe_subnet_id\" {\n"
            "  value = azurerm_subnet.pe.id\n"
            "}\n"
        )
    return base


def _build_tfvars_example(enable_observability: bool, network_tier: str) -> str:
    lines = [
        "resource_group_name = \"replace-me-rg\"",
        "location            = \"eastus\"",
        "environment         = \"dev\"",
        "workload_name       = \"starter-workload\"",
        f"enable_observability = {str(enable_observability).lower()}",
        "operations_email    = \"\"",
    ]
    if network_tier in ("vnet-integrated", "private"):
        lines.extend([
            "vnet_address_prefix = \"10.0.0.0/16\"",
            "app_subnet_prefix   = \"10.0.0.0/24\"",
        ])
    if network_tier == "private":
        lines.append("pe_subnet_prefix    = \"10.0.1.0/24\"")
    return "\n".join(lines) + "\n"


class TerraformAgent:
    name = "terraform"
    display_name = "HashiCorp Terraform (AzureRM)"
    file_extension = ".tf"

    def emit(self, ctx: IacEmitContext) -> IacEmitResult:
        ctx.infra_dir.mkdir(parents=True, exist_ok=True)
        _write_text(ctx.infra_dir / "providers.tf", _build_providers())
        _write_text(
            ctx.infra_dir / "variables.tf",
            _build_variables(ctx.enable_observability, ctx.network_tier),
        )
        _write_text(
            ctx.infra_dir / "main.tf",
            _build_main(ctx.enable_observability, ctx.network_tier),
        )
        _write_text(
            ctx.infra_dir / "outputs.tf",
            _build_outputs(ctx.enable_observability, ctx.network_tier),
        )
        _write_text(
            ctx.infra_dir / "terraform.tfvars.example",
            _build_tfvars_example(ctx.enable_observability, ctx.network_tier),
        )
        return IacEmitResult(
            files_written=[
                "infra/providers.tf",
                "infra/variables.tf",
                "infra/main.tf",
                "infra/outputs.tf",
                "infra/terraform.tfvars.example",
            ],
            deploy_bullets=[
                "- Copy `infra/terraform.tfvars.example` to `infra/terraform.tfvars` and edit values.",
                "- Initialize and apply: `cd infra && terraform init && terraform plan && terraform apply`.",
                "- Validate with: `terraform validate && terraform fmt -check`.",
            ],
        )


AGENT = TerraformAgent()
