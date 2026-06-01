# Fabric Medallion Pipeline

This sample project demonstrates a Bronze, Silver, and Gold data pipeline built with Azure-oriented service scaffolding, governance helpers, runnable tests, and Bicep infrastructure.

## Included Artifacts

- `diagrams/` architecture diagram and notes
- `docs/` business and project summary materials
- `src/` Bronze, Silver, Gold, orchestrator, and shared library code
- `infra/` Bicep modules and environment parameters
- `tests/` pipeline and helper validation

## Local Validation

```powershell
python -m pytest tests -v --tb=short --no-header
```

## Notes

This project is available as one sample in the broader Azure Architecture Factory portfolio. It is no longer the sole reference implementation for the repository.
