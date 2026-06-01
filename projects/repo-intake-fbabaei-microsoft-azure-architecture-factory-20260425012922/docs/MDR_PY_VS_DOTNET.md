# MDR Python vs .NET -- Scaffold Comparison

Two versions of the same BRD (`docs/intake/mdr-support.md`), same `extraction-chat`
archetype, different language agent.

| Project | Language | Package / Project name | Total files |
|---|---|---|---|
| `projects/mdr-support-20260421002041` | Python 3.11 / FastAPI | `mdr_support` | 28 |
| `projects/mdr-support-20260421003634` | .NET 8 / ASP.NET Core | `MdrSupport` | 31 |

Difference of 3 files is purely language-idiomatic packaging:
.NET adds `global.json`, `Dockerfile`, `.dockerignore`, `appsettings.json`,
`appsettings.Development.json`, plus a separate `Tests.csproj`; Python has
`pyproject.toml`, `requirements.txt`, and two `__init__.py` shims. The
domain surface area is identical.

## Domain parity

### Services (5-for-5)

| Concept | Python | .NET |
|---|---|---|
| Ingest raw upload -> text excerpt | `services/document_ingestion.py` | `Services/DocumentIngestionService.cs` |
| Extract structured fields | `services/extraction_service.py` | `Services/ExtractionService.cs` |
| Compute next missing clarification | `services/clarification_service.py` | `Services/ClarificationService.cs` |
| Persist drafts across turns | `services/repository.py` (`DraftRepository`) | `Services/DraftRepository.cs` |
| Record human-in-the-loop chat turns | `services/session_service.py` | `Services/SessionService.cs` |

### Endpoints (6-for-6 business + health)

| Endpoint | Python (`@app.*`) | .NET (`app.Map*`) |
|---|---|---|
| `GET  /health` | ✅ | ✅ |
| `GET  /health/ready` | -- | ✅ (per .NET factory convention) |
| `POST /documents/upload` | ✅ | ✅ |
| `POST /documents/{id}/chat` | ✅ | ✅ |
| `GET  /documents/{id}` | ✅ | ✅ |
| `GET  /documents/{id}/clarifications` | ✅ | ✅ |
| `POST /documents/{id}/draft` | ✅ 409 when fields missing | ✅ 409 when fields missing |

### Shared artifacts

Both versions emit the same set of non-source files:

- `docs/` -- architecture-overview, delivery-milestones, detailed-architecture,
  governance-model, guide-report, success-criteria, traceability-matrix
- `diagrams/<slug>.drawio` + `<slug>.md`
- `infra/main.bicep`
- `sample-corpus/` (README.md + manifest.json)
- `project-manifest.json` (both record `analysis.archetype = "extraction-chat"`)
- `README.md`, `DEPLOY.md`
- `scripts/select_model.ps1`

### Tests

- Python: `tests/test_generated_project.py` (pytest) -- asserts expected files
  exist per the archetype; exercises `/health`.
- .NET: `tests/HealthEndpointTests.cs` (xUnit + `WebApplicationFactory<Program>`) --
  exercises `/health`, `/health/ready`, and `GET /documents/{unknown}` -> 404.

## Determinism

Three consecutive .NET regens (`scripts/mdr_dotnet_3x.py`):

```
[run 0] slug=mdr-support-20260421003634        files=31 archetype=extraction-chat
[run 1] slug=mdr-support-20260421003634-rnet01 files=31 archetype=extraction-chat
[run 2] slug=mdr-support-20260421003634-rnet02 files=31 archetype=extraction-chat
[OK] 3x deterministic: 31 files, archetype=extraction-chat
```

All existing regression harnesses remain green:

- `dotnet_e2e_3x.py` -> 36/36 x 3 (file_count=27, api-service archetype)
- `default_path_e2e_3x.py` -> 13/13 x 3 (api-service archetype)
- `optout_infra_security_smoke.py` -> 6/6

## Takeaways

1. The factory produces **functionally equivalent scaffolds across languages**
   for the same archetype. A reviewer comparing the two trees sees the same
   concepts in the same places -- only the syntax changes.
2. Language-specific conventions are preserved: Python uses snake_case module
   layout under `src/mdr_support/`; .NET uses a PascalCase assembly
   (`MdrSupport`) with `Services/*.cs` + separate `Tests.csproj`.
3. The .NET agent follows the factory's own `.github/copilot-instructions.md`
   .NET conventions (minimal API, `/health` + `/health/ready` on port 8080,
   optional `AddApplicationInsightsTelemetry()` when observability is on).
4. Archetype routing is orthogonal to language routing: the generic
   `dotnet_e2e_3x` harness -- whose BRD contains no extraction keywords --
   still produces the 27-file `api-service` shape.
