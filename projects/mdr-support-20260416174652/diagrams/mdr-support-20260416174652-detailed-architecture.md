# MDR Support Detailed Architecture Diagram Notes

Companion notes for `mdr-support-20260416174652-detailed-architecture.drawio`.

## Diagram Pages

1. `MDR Support - Logical Architecture`
2. `MDR Support - Sequence Flows`
3. `MDR Support - Failure Paths`

## Coverage

1. Detailed component decomposition for Phase 1 extraction and clarification workflows.
2. End-to-end extraction sequence from upload to missing-field prompts.
3. Clarification loop sequence from user answers to draft readiness updates.
4. Failure scenarios across validation, dependency outage, persistence, and conflict resolution.

## Key Components Modeled

1. User roles and internal portal UI.
2. MDR API service and orchestration layer.
3. Document ingestion, extraction, validator, clarification manager, and draft builder.
4. AI dependencies (Document Intelligence and LLM extraction).
5. Storage/state dependencies (raw document store, session state, draft store, audit trail).

## Expected Outcomes

1. Clear view of Phase 1 target architecture beyond the generated starter.
2. Traceable flow for implementation planning and API contract design.
3. Explicit recovery paths for common runtime and integration failures.
