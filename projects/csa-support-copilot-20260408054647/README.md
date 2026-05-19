# **Business Requirements Document (BRD)**

Generated from BRD `csa-support-copilot.md` by local fallback orchestrator.

## What Was Generated
- `docs/architecture-overview.md`
- `docs/governance-model.md`
- `docs/delivery-milestones.md`
- `docs/success-criteria.md`
- `docs/traceability-matrix.md`
- `diagrams/csa-support-copilot-20260408054647.md`
- `diagrams/csa-support-copilot-20260408054647.drawio`
- `src/copilot_api/main.py`
- `src/copilot_api/models.py`
- `src/copilot_api/services/copilot_service.py`
- `requirements.txt`
- `DEPLOY.md`

## BRD Requirement Highlights
- Establish clear **business value**
- Align stakeholders on **scope and priorities**
- Provide guidance for **architecture and security reviews**
- Enable conversion into **VBD-aligned delivery artifacts**
- UI pixel-perfect design
- Model training details
- Low-level code implementation
- Provide a **single CSA-facing Copilot** for daily technical and operational needs
- Reduce cognitive load caused by tool and context switching
- Improve **speed, accuracy, and confidence** in CSA responses
- Enable reuse of CSA operational tools through MCP
- Natural language Q\&A for CSA operational and technical topics
- Aggregation of CSA tools into a **single MCP**
- Secure retrieval of approved internal documentation
- Step-by-step operational guidance
- Context-aware responses aligned to CSA scenarios
- Customer-facing deployment (internal only)
- External tenant access
- Autonomous decision-making without human oversight
- ✅ Improves CSA efficiency and scale
- ✅ Promotes reuse and standardization
- ✅ Supports AI-first CSA tooling strategy
- ✅ Demonstrates hands-on innovation and delivery

## Production Companion API (External Portal)

This project now includes a production-ready API baseline so it can run as a companion service to Azure Architecture Factory and be safely called from the external portal.

### Implemented Hardening

- API credential enforcement via `x-api-key` or `Authorization: Bearer <token>`
- Readiness probe (`/ready`) that validates production auth configuration
- Liveness probe (`/health`) for runtime checks
- Per-user sliding-window rate limiting for `/api/copilot/ask`
- Request correlation with `x-request-id` propagation
- CORS allow-list via environment configuration
- Tool catalog endpoint for portal feature discovery (`/api/copilot/tools`)

### Endpoints

- `GET /health`
- `GET /ready`
- `GET /api/copilot/tools`
- `POST /api/copilot/ask`

### Required Production Configuration

- `APP_ENV=prod`
- `APP_VERSION=1.0.0`
- `REQUIRE_API_KEY=true`
- `CSA_API_KEYS=<comma-separated-keys>`
- `ALLOWED_ORIGINS=https://<external-portal-host>`
- `RATE_LIMIT_PER_MINUTE=30`
