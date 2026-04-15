# Deploy

## Prerequisites
- Python 3.11+
- Azure CLI authenticated
- Target Azure subscription and resource group

## Local Validation
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest tests -q
```

## Local Run
```bash
python -m uvicorn src.copilot_api.main:app --host 127.0.0.1 --port 8000 --reload
```

## Azure Deployment Outline
1. Review and customize `infra/main.bicep`.
2. Provision hosting, identity, Key Vault access, Application Insights, and Log Analytics.
3. Configure application settings for the generated API.
4. Configure health probes, alerts, dashboards, and operational ownership for the generated workload.
5. Deploy the project from `projects/architecture-flow-test-multi-service-retail-intelligence-platform-20260415052731`.
6. Validate `/health` after deployment and confirm telemetry reaches Azure Monitor.
