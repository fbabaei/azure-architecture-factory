# Field Service Intelligence Platform - Architecture Overview

## Target Architecture
This starter architecture packages the submitted BRD into a generated project scaffold that can be refined for Azure deployment.

## Requirement Signals
- Average response time 4–6 hours due to mis-routing
- 22% first-visit failure rate — technicians arrive without correct parts or skills
- No SLA tracking per work-order type
- 35% of field dispatches are reactive emergency calls that could have been predicted
- High parts cost due to unplanned failure events
- Customer SLA penalties for unplanned downtime
- Average resolution time 2.1× higher for unfamiliar asset types
- Knowledge concentrated in senior technicians — no knowledge transfer path

## Recommended Building Blocks
- Presentation or workflow entry point
- Integration API layer
- Data or document store
- Observability with Application Insights and Log Analytics
- Identity, secrets, and governance controls

## Network Topology
- **Network Tier**: Public (internet-facing, no VNet isolation)

## Capability Coverage
- Azure OpenAI: Yes
- Microsoft Copilot: Yes
- Machine Learning lifecycle: Yes
- Governance controls: Yes
