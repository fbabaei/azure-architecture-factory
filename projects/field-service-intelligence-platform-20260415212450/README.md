# Field Service Intelligence Platform

Generated from BRD `fb-app-1.md` by the Azure-native factory runner.

## What Was Generated
- `docs/architecture-overview.md`
- `docs/governance-model.md`
- `docs/delivery-milestones.md`
- `docs/success-criteria.md`
- `docs/traceability-matrix.md`
- `diagrams/field-service-intelligence-platform-20260415212450.md`
- `diagrams/field-service-intelligence-platform-20260415212450.drawio`
- `src/copilot_api/main.py`
- `src/copilot_api/models.py`
- `src/copilot_api/services/copilot_service.py`
- `requirements.txt`
- `infra/main.bicep`
- `tests/test_generated_project.py`

## Selected Generation Options
- Monitoring and observability wiring requested: No

## BRD Requirement Highlights
- Average response time 4–6 hours due to mis-routing
- 22% first-visit failure rate — technicians arrive without correct parts or skills
- No SLA tracking per work-order type
- 35% of field dispatches are reactive emergency calls that could have been predicted
- High parts cost due to unplanned failure events
- Customer SLA penalties for unplanned downtime
- Average resolution time 2.1× higher for unfamiliar asset types
- Knowledge concentrated in senior technicians — no knowledge transfer path
- Customer satisfaction (CSAT) scoring 12 points below industry benchmark
- GDPR and SOC 2 exposure for customer PII in work records
