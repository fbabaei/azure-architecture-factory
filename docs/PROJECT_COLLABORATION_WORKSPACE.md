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
- notes

The portal exposes this state through:

- `GET /api/projects/{slug}/collaboration`
- `POST /api/projects/{slug}/collaboration`

## Future phases

- Integrate Teams channel/chat links.
- Add approval workflow history.
- Add Waza/eval evidence links.
- Add notification and assignment support.
