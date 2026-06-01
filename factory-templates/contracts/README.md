# AAF Inter-Agent Contracts

Formal JSON Schema contracts that travel between the three conceptual layers of the Azure Architecture Factory pipeline.

```
[User Input]
     ↓  intake-contract.schema.json
[Intake Layer]      → brd-to-architecture-diagram (extract-inventory)
     ↓  design-contract.schema.json
[Design Layer]      → brd-to-architecture-diagram, drawio-architecture-reader
     ↓  architecture-contract.schema.json
[Architecture Layer] → azure-architecture-implementer, source-code-maintainer,
                       bicep / terraform validators, security-compliance-auditor,
                       production-environment-advisor, azure-project-deployer
     ↓
[Final Output: production-ready project under projects/<slug>/]
```

## Why these exist

The scoping audit identified three gaps in AAF:

1. **Implicit contracts** between agents — fixed by these schemas.
2. **No separation between generation and validation** — fixed by the new
   [`contract-validator`](../../.github/agents/contract-validator.agent.md)
   agent that uses these schemas as gates.
3. **No conceptual layering** mapped onto the 20 real agents — fixed by
   [`docs/AAF_AGENT_SCOPING.md`](../../docs/AAF_AGENT_SCOPING.md).

## Files

| File | Layer | Produced by | Consumed by |
|------|-------|-------------|-------------|
| [`intake-contract.schema.json`](./intake-contract.schema.json) | Intake | Portal BRD intake / `modernization-to-factory` Phase 4 | `brd-to-architecture-diagram`, `project-orchestrator` Phase 0 |
| [`design-contract.schema.json`](./design-contract.schema.json) | Design | `brd-to-architecture-diagram`, `drawio-architecture-reader` | `azure-architecture-implementer`, all Phase 2.x gates |
| [`architecture-contract.schema.json`](./architecture-contract.schema.json) | Architecture | Phase 2 + 2.5–2.8 + 3 outputs aggregated by `project-state-manager` | `azure-project-deployer`, `factory-handoff`, `project-traceability-advisor` |

## Validation

The `contract-validator` agent validates each contract at phase boundaries:

```
Phase 0  → intake-contract        (gate before Phase 1)
Phase 1  → design-contract         (gate before Phase 2)
Phase 3  → architecture-contract   (gate before Phase 4 / deploy)
```

Validation is non-destructive: it produces `projects/<slug>/docs/contracts/<phase>-validation.json` with a pass/fail verdict plus structured findings. The orchestrator must not advance past a gate with `status: "fail"`.

## Versioning

Schemas are versioned via the `$id` URI suffix (`/v1/...`). Breaking changes increment the major version. Generated projects record the contract version they were built against in `project-manifest.json → contracts.versions`.
