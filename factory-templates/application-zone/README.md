# Application Zone App Packs

This directory stores versioned App Pack manifests used by AAF to create applications.

Design principle:
- AAF creates and exports apps.
- Exported apps execute independently and do not depend on AAF runtime services.

Current pack layout:
- packs/<packId>/<version>/manifest.json

Example:
- packs/casewright/1.0.0/manifest.json

## Independent Shipping Workflow

Use these MCP tools in sequence to create a standalone application bundle:

1. `export_application_pack`
- Exports app code + infra into `outputs/application-zone/<pack>-<version>-<timestamp>/`

2. `generate_application_pack_parameters`
- Validates pack inputs and writes profile-specific parameter files to:
	- `deploy/parameters/deployment-parameters.<profile>.json`
	- `deploy/parameters/<profile>.generated.bicepparam`
	- `deploy/parameters/application-inputs.<profile>.json`

3. `generate_application_pack_deploy_commands`
- Writes deployment scripts to:
	- `deploy/commands/deploy-<profile>.ps1`
	- `deploy/commands/deploy-<profile>.sh`

After generation, teams can deploy and run the exported application independently of AAF.
