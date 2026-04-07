# Deploy

## Local Validation

1. Verify required docs and diagrams exist.
2. Run tests from the project root:

```bash
python -m pytest tests -q
```

## Azure Deployment Notes

- Host API and orchestration components in Azure App Service or Azure Container Apps.
- Use Azure OpenAI for intent classification and response guidance.
- Store prompts and configuration in Azure App Configuration and Key Vault.
- Publish telemetry to Application Insights and Log Analytics.
