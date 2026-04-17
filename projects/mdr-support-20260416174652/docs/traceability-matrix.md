# MDR Support - Requirements Traceability

| Requirement | BRD Signal | Implemented In | Status |
|-------------|------------|----------------|--------|
| REQ-001 | Compliance agent for MDR arrangement creation with MDR-specific Q&A | `POST /qa` in `src/mdr_agent/main.py`; `src/mdr_agent/services/qa_service.py` (Azure OpenAI + local fallback); `docs/architecture-overview.md` | Implemented |
| REQ-002 | File upload-based extraction (PDFs + text) | `POST /arrangements/upload` in `src/mdr_agent/main.py`; `src/mdr_agent/services/document_ingestion.py`; `src/mdr_agent/services/extraction_agent.py` | Implemented |
| REQ-003 | Interactive, human-in-the-loop chat guiding arrangement creation | `POST /arrangements/{id}/chat` in `src/mdr_agent/main.py`; `src/mdr_agent/services/chat_session.py` | Implemented |
| REQ-004 | Structured MDR arrangement JSON output | `src/mdr_agent/models.py` (`MDRArrangement`); `POST /arrangements/{id}/draft` | Implemented |
| REQ-005 | Intelligent clarification loop identifying missing mandatory fields | `src/mdr_agent/services/clarification_service.py`; `MANDATORY_FIELDS` in `models.py` | Implemented |
| REQ-006 | Reusable extraction patterns for MDR modernization roadmap | Service layer split in `src/mdr_agent/services/`; tests in `tests/test_generated_project.py` | Implemented |
| REQ-007 | Batch / multi-arrangement processing deferred to a later phase | Not implemented - documented as out of scope in `docs/detailed-architecture.md` | Deferred (by design) |
| REQ-008 | Azure governance, secrets, identity | `infra/main.bicep` (Managed Identity, Key Vault, RBAC wiring) | Implemented |
| REQ-009 | Testable end-to-end flows | `tests/test_generated_project.py` covers upload -> clarifications -> chat -> draft | Implemented |
