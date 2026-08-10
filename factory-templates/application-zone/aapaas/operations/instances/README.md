# AAPAAS managed instances

This folder tracks deployed or discovered app-pack instances managed by AAPAAS.

## Current CaseWright finding

Azure contains multiple CaseWright infrastructure resource sets, but the current discovery did not find a live Container Apps/API runtime in the likely resource groups.

Primary candidate instance:

- Instance: `casewright-dev-eastus`
- Resource group: `rg-dev-eastus`
- Location: `eastus`
- Status: `infrastructure-discovered-runtime-missing`

Use `scripts\Discover-CaseWrightResources.ps1` to refresh discovery evidence.
