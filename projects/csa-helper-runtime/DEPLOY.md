# Deploying csa-helper-runtime

> ⚠️ **This orchestrator run did NOT deploy.** The steps below are reference only.

## Prerequisites
- Azure CLI ≥ 2.55, Bicep ≥ 0.32. Run `az bicep upgrade` if needed.
- Subscription containing `rg-fbabaei-2653` (where the existing AOAI lives).
- Signed-in principal with:
  - `Contributor` on the target deployment RG, **and**
  - `User Access Administrator` on `rg-fbabaei-2653` (required to create the cross-RG role assignment on `fbfoundrywestus`).
- The existing AOAI account `fbfoundrywestus` has a `gpt-4o` model deployment.

## Variables
```pwsh
$rg = "csa-helper-runtime-dev-rg"
$loc = "eastus2"
```

## 1. Create the deployment RG
```pwsh
az group create --name $rg --location $loc
```

## 2. First deployment (boots platform with hello-world image)
```pwsh
az deployment group create `
  --resource-group $rg `
  --template-file projects\csa-helper-runtime\infra\main.bicep `
  --parameters projects\csa-helper-runtime\infra\params\dev.bicepparam `
  --name csa-helper-runtime-bootstrap
```

This creates ACR, Container Apps Env, Container App (running the public hello-world image), Key Vault (with `aoai-endpoint`), UAMI, Log Analytics, App Insights, and the cross-RG role assignment on `fbfoundrywestus`.

## 3. Build and push the runtime image
```pwsh
$acrLogin = az deployment group show -g $rg -n csa-helper-runtime-bootstrap --query "properties.outputs.acrLoginServer.value" -o tsv
$acrName = $acrLogin.Split('.')[0]

az acr login --name $acrName
docker build -t "$acrLogin/csa-helper-runtime:v1" `
  --build-arg CSA_HELPER_REF=main `
  -f projects\csa-helper-runtime\Dockerfile projects\csa-helper-runtime
docker push "$acrLogin/csa-helper-runtime:v1"
```

(Or use ACR Tasks: `az acr build -r $acrName -t csa-helper-runtime:v1 -f Dockerfile projects\csa-helper-runtime`.)

## 4. Redeploy with the runtime image
Edit `projects\csa-helper-runtime\infra\params\dev.bicepparam` and set:
```bicep
param containerImage = '<acr-login-server>/csa-helper-runtime:v1'
```
Then re-run the deployment from step 2.

## 5. Smoke test
```pwsh
$fqdn = az deployment group show -g $rg -n csa-helper-runtime-bootstrap --query "properties.outputs.containerAppFqdn.value" -o tsv
curl "https://$fqdn/health"
curl "https://$fqdn/health/ready"
curl -X POST "https://$fqdn/ask" -H "content-type: application/json" `
     -d '{"prompt":"Customer wants a Foundry POC milestone next week"}'
```

## 6. Verify no secrets leak
```pwsh
az containerapp show -g $rg -n csa-helper-runtime `
  --query "properties.template.containers[0].env" -o json
# AZURE_OPENAI_ENDPOINT must reference secret 'aoai-endpoint' (no plaintext URL).
```

## Rollback
```pwsh
az deployment group delete -g $rg -n csa-helper-runtime-bootstrap
az group delete -n $rg --yes --no-wait
# The cross-RG role assignment on fbfoundrywestus is removed automatically when
# the UAMI is deleted (the assignment is scoped to the AOAI account).
```
