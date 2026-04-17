#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build the factory portal Docker image, push to ACR, and update the
    Azure Container App to the new revision.

.DESCRIPTION
    Usage:
        .\scripts\build_and_deploy_portal.ps1
        .\scripts\build_and_deploy_portal.ps1 -SkipBuild      # re-deploy latest without rebuilding
        .\scripts\build_and_deploy_portal.ps1 -DryRun         # print commands without running them

.PARAMETER SkipBuild
    Skip the docker build + push steps and just update the Container App
    to use whatever image is already tagged :latest in ACR.

.PARAMETER DryRun
    Print each command without executing it.
#>
param(
    [switch]$SkipBuild,
    [switch]$DryRun
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Config ──────────────────────────────────────────────────────────────────
$DOCKER       = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$ACR          = "archfactorydevacr.azurecr.io"
$REPO         = "$ACR/portal"
$TAG          = "portal-$(Get-Date -Format 'yyyyMMddHHmmss')"
$IMAGE_TAGGED = "${REPO}:${TAG}"
$IMAGE_LATEST = "${REPO}:latest"
$APP_NAME     = "arch-factory-dev-portal"
$RG           = "arch-factory-dev-rg"
$DOCKERFILE   = Join-Path $PSScriptRoot "..\Dockerfile.portal"
$CONTEXT      = Join-Path $PSScriptRoot ".."
# ────────────────────────────────────────────────────────────────────────────

function Invoke-Step {
    param([string]$Label, [scriptblock]$Block)
    Write-Host "`n==> $Label" -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "    [DRY RUN - skipped]" -ForegroundColor Yellow
    } else {
        & $Block
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Step failed: $Label (exit $LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    }
}

# ── 1. Verify Docker daemon is running ──────────────────────────────────────
if (-not $SkipBuild) {
    Write-Host "Checking Docker daemon..." -ForegroundColor Gray
    $dockerInfo = & $DOCKER info --format "{{.ServerVersion}}" 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dockerInfo)) {
        Write-Error "Docker daemon is not running. Start Docker Desktop and retry."
        exit 1
    }
    Write-Host "Docker server: $dockerInfo" -ForegroundColor Green
}

# ── 2. ACR login ────────────────────────────────────────────────────────────
Invoke-Step "ACR login" {
    az acr login --name archfactorydevacr
}

# ── 3. Build image ──────────────────────────────────────────────────────────
if (-not $SkipBuild) {
    Invoke-Step "Build $IMAGE_TAGGED" {
        & $DOCKER build `
            --file $DOCKERFILE `
            --tag $IMAGE_TAGGED `
            --tag $IMAGE_LATEST `
            $CONTEXT
    }

    # ── 4. Push both tags ───────────────────────────────────────────────────
    Invoke-Step "Push $IMAGE_TAGGED" {
        & $DOCKER push $IMAGE_TAGGED
    }
    Invoke-Step "Push ${REPO}:latest" {
        & $DOCKER push $IMAGE_LATEST
    }
} else {
    Write-Host "SkipBuild set — using existing :latest in ACR" -ForegroundColor Yellow
    $IMAGE_TAGGED = $IMAGE_LATEST
}

# ── 5. Update Container App ─────────────────────────────────────────────────
Invoke-Step "Update Container App '$APP_NAME' -> $IMAGE_TAGGED" {
    az containerapp update `
        --name $APP_NAME `
        --resource-group $RG `
        --image $IMAGE_TAGGED `
        --output none
}

# ── 6. Print live URL ────────────────────────────────────────────────────────
Write-Host "`n==> Portal URL" -ForegroundColor Cyan
$fqdn = az containerapp show `
    --name $APP_NAME `
    --resource-group $RG `
    --query "properties.configuration.ingress.fqdn" -o tsv 2>&1
Write-Host "https://$fqdn" -ForegroundColor Green
Write-Host "`nDone. Image: $IMAGE_TAGGED" -ForegroundColor Green
