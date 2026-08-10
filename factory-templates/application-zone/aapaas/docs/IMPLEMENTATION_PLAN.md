# Step-by-step implementation plan

## Phase 0 - Confirm scope and operating model

1. Name the service: AI Apps as a Service.
2. Position the service as a factory plus app-pack catalog plus deployment and operations layer.
3. Confirm the first delivery target is an internal MVP, not an external marketplace.
4. Confirm the first certified app pack is CaseWright.
5. Confirm the initial candidate packs are Compliance Agent, Supply Chain Control Tower, and Mailer Automation.

## Phase 1 - Establish the service control plane

1. Use Azure Architecture Factory as the control plane for intake, app-pack catalog, deployment orchestration, and lifecycle state.
2. Reuse the Application Zone product brief and technical blueprint copied into `control-plane\application-zone\docs`.
3. Reuse the Application Zone export and deployment helper tools copied into `control-plane\application-zone\tools`.
4. Standardize service states:
   - Draft
   - Validating
   - Provisioning
   - Healthy
   - Degraded
   - Upgrading
   - RollbackInProgress
   - Failed

## Phase 2 - Define the app-pack contract

1. Ratify `catalog\app-pack.schema.json` as the contract for all app packs.
2. Require semantic versioning for every pack.
3. Require each pack to define:
   - Metadata
   - Compatibility
   - Inputs
   - Deployment profiles
   - Security controls
   - Operations targets
   - Lifecycle strategy
   - Packaging/export rules
   - Verification artifacts
4. Block certification until the pack has a health endpoint, smoke test path, deployment path, and rollback statement.

## Phase 3 - Build the catalog

1. Use `catalog\service-catalog.json` as the source of truth for visible service offerings.
2. Add only certified or candidate app packs to the catalog.
3. Keep source repo locations in `catalog\source-repos.json`.
4. Separate active packs from references, learning repos, and archived repos.

## Phase 4 - Certify CaseWright as the first production pack

1. [x] Validate the copied CaseWright manifest at `app-packs\casewright\1.0.0\manifest.json`.
2. [x] Confirm exported assets exist in `C:\dev\workspace\casewright`.
3. [x] Confirm infra, deployment, health, docs, scripts, tests, and Teams/web channels are present.
4. [x] Generate sample deployment parameters for the dev profile.
5. [x] Generate sample deploy commands for the dev profile.
6. [ ] Run smoke tests and starter evals against a real deployed dev instance.
7. [x] Mark CaseWright as the certified seed pack for this scaffold.

## Phase 5 - Convert candidate repos into app packs

1. [x] For each candidate repo, complete the manifest under `app-packs\<pack-id>\<version>\manifest.json`.
2. [x] Add initial export includes, health endpoints where present, smoke test references, and eval plan references.
3. [x] Map repo-specific deployment requirements into the common app-pack contract.
4. [x] Run the certification checklist and generate reports under `certification\reports`.
5. [ ] Promote packs from candidate to preview or certified only after gap remediation.

## Phase 6 - Add governance gates

1. Enforce managed identity wherever possible.
2. Require Key Vault for secrets.
3. Require least-privilege RBAC.
4. Require diagnostic logs, application telemetry, and audit trail.
5. Require responsible AI review for every app pack.
6. Require a data-boundary statement before deployment.
7. Require a human approval gate for high-impact or regulated actions.

## Phase 7 - Add day-2 operations

1. Define SLOs and health checks per pack.
2. Track deployed instances, deployment runs, policy check results, upgrade runs, and rollback runs.
3. Add runbooks for incident triage, app-pack upgrade, rollback, and cost review.
4. Add usage, quality, cost, latency, and failure dashboards.
5. Run periodic evals and publish improvement actions.

## Phase 8 - Build the portal experience

1. Add an Application Zone catalog page.
2. Add a deployment wizard that reads pack manifests.
3. Add validation and policy precheck APIs.
4. Add provisioning status and run history.
5. Add instance inventory and health views.
6. Add upgrade and rollback actions.

## Phase 9 - Pilot

1. Pilot with two teams.
2. Measure median time to healthy deployed instance.
3. Track first-attempt deployment success rate.
4. Track policy violations prevented before deploy.
5. Track time to first useful answer.
6. Track upgrade success without rollback.
7. Collect pilot satisfaction score.

## Phase 10 - Scale

1. Harden the control plane.
2. Add contribution guidance for new app packs.
3. Add compatibility matrix and release checklist.
4. Add support tier definitions.
5. Add chargeback or cost-allocation model.
6. Promote the service as a repeatable AI app delivery platform.
