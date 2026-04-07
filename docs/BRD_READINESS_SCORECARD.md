# BRD Readiness Scorecard

Use this one-page scorecard before sending a BRD to Azure Architecture Factory.

Reference guidance: [BRD_READINESS_GATE.md](BRD_READINESS_GATE.md)

## Scoring Scale

- `2` = Pass
- `1` = Partial
- `0` = Fail

## BRD Information

- BRD name:
- Owner:
- Review date:
- Reviewer:
- Target workload type:
- Target environment:

## Weighted Scorecard

Record each item as:

- `Score`: `0`, `1`, or `2`
- `Weighted Score`: `Weight x Score`

### Scope

- Primary business outcome is explicit
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Main users, systems, or personas are identified
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Core capabilities are bounded and specific
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Success criteria are stated
  - Weight: `1`
  - Score:
  - Weighted Score:
  - Notes:

### Workload Shape

- Target workload type is recognizable
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Interaction model is clear
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Service boundaries or domains can be inferred
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Request is not a vague combination of unrelated systems
  - Weight: `1`
  - Score:
  - Weighted Score:
  - Notes:

### Azure Fit

- Azure is explicitly required or clearly acceptable
  - Weight: `3`
  - Score:
  - Weighted Score:
  - Notes:
- Hosting model maps to Azure services
  - Weight: `3`
  - Score:
  - Weighted Score:
  - Notes:
- Required integrations are Azure-compatible
  - Weight: `3`
  - Score:
  - Weighted Score:
  - Notes:
- No hard dependency contradicts Azure-first delivery
  - Weight: `3`
  - Score:
  - Weighted Score:
  - Notes:

### Data

- Main data entities or documents are named
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Inputs and outputs are identified
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- External integrations are described
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Data sensitivity or classification is mentioned
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:

### NFRs

- Security expectations are stated
  - Weight: `3`
  - Score:
  - Weighted Score:
  - Notes:
- Availability or resiliency expectations are stated
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Monitoring or operational visibility is expected
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Environment expectations are stated
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:

### Delivery Readiness

- Enough detail exists to create a diagram
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Enough detail exists to scaffold source structure
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Enough detail exists to generate infra assumptions
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:
- Enough detail exists to derive testable paths
  - Weight: `2`
  - Score:
  - Weighted Score:
  - Notes:

## Totals

- Maximum weighted score: `102`
- Actual weighted score:
- Percentage score:

Formula:

$$
  ext{Percentage} = \frac{\text{Actual Weighted Score}}{102} \times 100
$$

## Automatic Decision Rule

Mark any blocking condition first:

- Any `0` in `Azure Fit` = blocking
- Missing identity, compliance, or network ownership = blocking
- More than 2 total `0` scores = blocking

Decision:

- `Auto-Ready`
  - No blocking condition
  - Percentage score >= 80
- `Auto-Ready With Guardrails`
  - No Azure Fit block
  - Percentage score from 60 to 79
- `Architect Review Required`
  - Any blocking condition
  - Or percentage score < 60

## Review Summary

- Final classification:
- Main blockers:
- Main assumptions:
- Required clarifications before orchestration:
- Can this BRD go directly to `project-orchestrator`?

## Quick Recommendation Text

Use one of these summaries verbatim:

- `This BRD is Auto-Ready for Azure Architecture Factory and can proceed directly to project orchestration.`
- `This BRD is Auto-Ready With Guardrails. Generate the baseline, but require architecture review before deployment approval.`
- `This BRD requires architect review before Azure Architecture Factory should be used as the implementation engine.`
