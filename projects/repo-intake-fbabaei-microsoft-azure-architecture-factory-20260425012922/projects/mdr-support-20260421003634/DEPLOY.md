# Deploy

## Prerequisites
- .NET 8 SDK
- Docker Desktop (or compatible container runtime)
- Azure CLI authenticated
- Target Azure subscription and resource group

## Local Validation
```bash
cd src
dotnet restore MdrSupport.csproj
dotnet build MdrSupport.csproj -c Release
cd ../tests
dotnet test MdrSupport.Tests.csproj -c Release --no-restore
```

## Local Run
```bash
cd src
dotnet run --project MdrSupport.csproj
# Service listens on http://localhost:8080 (ASPNETCORE_URLS)
# curl http://localhost:8080/health
```

## Azure Deployment Outline
1. Review and customize the infrastructure templates under `infra/`.
2. Provision hosting (Container Apps), user-assigned managed identity, Key Vault access, Application Insights, and Log Analytics.
3. Configure app settings via `ASPNETCORE_*` and `APPLICATIONINSIGHTS_CONNECTION_STRING`; use DefaultAzureCredential for Azure SDK clients.
4. Build & push the container image: `docker build -t <registry>/mdr-support-20260421003634:latest src/ && docker push <registry>/mdr-support-20260421003634:latest`.
5. Deploy the project from `projects/mdr-support-20260421003634`.
6. Validate `/health` and `/health/ready` after deployment.
7. Smoke-test the extraction flow: `curl -F file=@sample-corpus/sample.txt https://<host>/documents/upload`.
8. Confirm Application Insights is receiving request + dependency telemetry and that alerts fire.
