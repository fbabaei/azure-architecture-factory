# Alignment Convergence Report — csa-helper-runtime

Iterations executed: **3** (minimum). Final status: **converged**. `gaps_found = 0` for iterations 2 and 3.

## 3-Way Inventory (final iteration)

| Component | BRD | Diagram | Code / Infra |
|---|---|---|---|
| Container App (`csa-helper-runtime`, port 8080) | FR-2, §5 | `capp` | `src/api/main.py`, `infra/modules/compute/containerapp.bicep` |
| Container Apps Environment | §5 | `cae` | `infra/modules/compute/containerappenv.bicep` |
| User-assigned MI (single, AOAI + KV + ACR) | FR-4, NFR-5, §5 | `uami` | `infra/modules/identity/managed-identity.bicep` |
| ACR (Basic) + AcrPull on UAMI | §5 | `acr` | `infra/modules/compute/acr.bicep` |
| Key Vault (RBAC) holding `aoai-endpoint` | NFR-4, FR-5, §5 | `kv` | `infra/modules/security/keyvault.bicep` |
| Log Analytics (30-day) | NFR-3, §5 | `law` | `infra/modules/monitoring/log-analytics.bicep` |
| App Insights (workspace-based) | NFR-3, FR-6, §5 | `ai` | `infra/modules/monitoring/appinsights.bicep` |
| Existing AOAI account (RBAC only) | §5 (explicit), §7 (no new AOAI) | `aoai` (yellow group) | `infra/modules/rbac/aoai-role-assignment.bicep` (cross-RG) |
| Cog. Services OpenAI User on AOAI | NFR-5, FR-4 | edge `e9` | `aoai-role-assignment.bicep` |
| Key Vault Secrets User on KV | NFR-5 | edge `e5` | `keyvault.bicep` |
| AcrPull on ACR | (implicit §5) | edge `e2` | `acr.bicep` |
| `POST /ask`, `GET /health`, `GET /health/ready` | FR-1, FR-2 | `e1` | `src/api/main.py` |
| FR-6 custom event w/ 5 dimensions | FR-6 | `e6` | `src/api/main.py::ask` |
| Reuse of `build_team.py` unchanged | FR-3, §7 | n/a | `Dockerfile` (vendor + symlink only) |
| Auto-scale 0–3 on HTTP concurrency | NFR-2 | n/a | `containerapp.bicep::scale` |
| 30-day Log Analytics retention | NFR-3 | n/a | `log-analytics.bicep::retentionInDays = 30` |

## Final Gaps
- `missing_from_diagram`: **0**
- `missing_from_code`: **0**
- `orphaned_in_code`: **0**
- `nfr_gaps`: **0** (all 5 NFRs traced)

## Fixes Applied During Loop
- None — first iteration converged. Iterations 2–3 were confirmation-only.
