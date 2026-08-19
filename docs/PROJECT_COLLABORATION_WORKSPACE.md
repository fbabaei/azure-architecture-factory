# Project Collaboration Workspace

## Purpose

The Project Collaboration Workspace gives everyone participating in a project a shared place to understand the project, coordinate work, review artifacts, and track decisions.

## MVP areas

- **Project Home**: project goal, current status, generated-from source, and latest milestone.
- **People & Roles**: default collaboration roles for owner, architect, implementer, reviewer, and approver.
- **Work Board**: lightweight work lanes for next actions, in-review items, blockers, and completed evidence.
- **Artifacts**: links to generated README, architecture overview, diagram, code browser, deployment guide, cost tools, and operations tools.
- **Decision Log**: decision records with owner, status, rationale, and evidence links.

## Data model

The workspace derives project metadata from `factory-projects.generated.json` and persists collaboration state per project under:

`factory-templates/application-zone/aapaas/operations/collaboration/<project-slug>.collaboration.json`

The persisted state includes:

- participants
- work items
- decisions
- Teams/project communication links
- meeting notes and discussion links
- evidence links
- Teams provisioning requests
- notification/action requests
- collaboration-specific permissions
- notes

The portal exposes this state through:

- `GET /api/projects/{slug}/collaboration`
- `POST /api/projects/{slug}/collaboration`

## Onboarding an existing project

Use **Project Collaboration Workspace > Onboard an existing project** to register a project that was created outside the portal.

The portal posts to `POST /api/projects/onboard` and creates:

- a project feed entry in `factory-projects.generated.json`
- a lightweight `projects/<slug>/project-manifest.json`
- starter project artifacts when links are not supplied
- default per-project collaboration state
- a best-effort owner assignment for Entra-filtered deployments

After onboarding, the project appears in the collaboration project dropdown and can use the same participants, work board, artifact review, and decision log features as generated projects.

## Collaboration recommendation coverage

Implemented collaboration enhancements:

- persistent per-project collaboration state
- project-level Teams/chat/channel links
- editable work board fields for owner, due date, status, blocker, and evidence
- decision metadata for approver, date, rationale, status, and evidence
- participant management with reviewer/approver flags
- meeting notes and discussion links
- evidence links for Waza evals, architecture reviews, deployment checks, cost reviews, and readiness reports
- export/share summary that can be copied for project reviews
- Teams provisioning request tracking
- notification/action request tracking
- collaboration-specific owners, editors, and viewers with server-side edit enforcement in Entra mode

Remaining future enhancements:

- live Microsoft Graph Teams chat/channel creation
- live outbound Teams/email notifications to owners and reviewers

## Future phases

- Add approval workflow history.
- Add Microsoft Graph-backed Teams provisioning.
- Add outbound notification delivery after user-approved message templates are defined.
