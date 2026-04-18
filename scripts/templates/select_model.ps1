<#
.SYNOPSIS
    Interactive Azure OpenAI model picker for a factory-generated project.

.DESCRIPTION
    Shows a table of chat models with approximate prices and trade-offs,
    lets the user pick one, and applies the change either to a local .env
    file (for local dev) or to a running Azure Container App.

    This script is shipped by the Azure Architecture Factory in every
    generated project. Adjust the model catalog below for your workload.

.PARAMETER Target
    Where to apply the change:
      - local    : update .env in the project root (default)
      - azure    : update the deployed Container App via `az containerapp update`
      - both     : update both

.PARAMETER ContainerApp
    Name of the Azure Container App (required when Target is azure or both).

.PARAMETER ResourceGroup
    Azure resource group of the Container App.

.PARAMETER EnvVarName
    The env var the app reads the model deployment name from.
    Defaults to AZURE_OPENAI_DEPLOYMENT (factory convention).

.EXAMPLE
    .\scripts\select_model.ps1
    .\scripts\select_model.ps1 -Target azure -ContainerApp my-app -ResourceGroup my-rg

.NOTES
    Prices are *rough* Azure OpenAI list prices per 1M tokens (USD, Apr 2026).
    Verify at https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
#>

[CmdletBinding()]
param(
    [ValidateSet('local', 'azure', 'both')]
    [string]$Target = 'local',

    [string]$ContainerApp,

    [string]$ResourceGroup,

    [string]$EnvVarName = 'AZURE_OPENAI_DEPLOYMENT'
)

$ErrorActionPreference = 'Stop'

# Project root = parent of this scripts/ folder
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile     = Join-Path $ProjectRoot '.env'

# --------------------------------------------------------------------------
# Model catalog - tune for your workload
# --------------------------------------------------------------------------
$Models = @(
    [pscustomobject]@{
        Key = 'gpt-5.2';       Deployment = 'gpt-5.2'
        InputPer1M = 5.00;     OutputPer1M = 15.00
        Tier = 'Premium'
        Strengths = 'Best reasoning, vision, largest context. Production default.'
        Tradeoffs = 'Highest cost. Overkill for simple Q&A.'
    },
    [pscustomobject]@{
        Key = 'gpt-5.2-mini';  Deployment = 'gpt-5.2-mini'
        InputPer1M = 0.30;     OutputPer1M = 1.20
        Tier = 'Balanced'
        Strengths = '~10x cheaper than gpt-5.2, still strong on extraction/RAG.'
        Tradeoffs = 'Slightly weaker on complex multi-step reasoning.'
    },
    [pscustomobject]@{
        Key = 'gpt-4o';        Deployment = 'gpt-4o'
        InputPer1M = 2.50;     OutputPer1M = 10.00
        Tier = 'Standard'
        Strengths = 'Mature, vision-capable, good quality.'
        Tradeoffs = 'Older than gpt-5.2; no longer state-of-the-art.'
    },
    [pscustomobject]@{
        Key = 'gpt-4o-mini';   Deployment = 'gpt-4o-mini'
        InputPer1M = 0.15;     OutputPer1M = 0.60
        Tier = 'Cheapest'
        Strengths = 'Cheapest paid option. Fast. Good for dev/test or high-volume simple chat.'
        Tradeoffs = 'Lower accuracy on complex tasks. Not recommended for prod.'
    },
    [pscustomobject]@{
        Key = 'o4-mini';       Deployment = 'o4-mini'
        InputPer1M = 1.10;     OutputPer1M = 4.40
        Tier = 'Reasoning'
        Strengths = 'Strong step-by-step reasoning. Good for agentic workflows.'
        Tradeoffs = 'Slower latency. No vision.'
    }
)

# --------------------------------------------------------------------------
# Render table
# --------------------------------------------------------------------------
Write-Host ''
Write-Host 'Azure OpenAI - Model Selector' -ForegroundColor Cyan
Write-Host ('-' * 60) -ForegroundColor DarkGray
Write-Host ''

for ($i = 0; $i -lt $Models.Count; $i++) {
    $m = $Models[$i]
    $idx = $i + 1
    $priceLine = ('Input ${0,5:N2} / Output ${1,5:N2} per 1M tokens' -f $m.InputPer1M, $m.OutputPer1M)

    Write-Host ("[{0}] {1,-14} " -f $idx, $m.Key) -ForegroundColor Yellow -NoNewline
    Write-Host ("({0})" -f $m.Tier) -ForegroundColor Green
    Write-Host ("    {0}" -f $priceLine) -ForegroundColor White
    Write-Host ("    + {0}" -f $m.Strengths) -ForegroundColor Gray
    Write-Host ("    - {0}" -f $m.Tradeoffs) -ForegroundColor DarkGray
    Write-Host ''
}

Write-Host ('-' * 60) -ForegroundColor DarkGray
Write-Host 'Note: prices are approximate Azure OpenAI list prices (USD, Apr 2026).' -ForegroundColor DarkGray
Write-Host 'Verify at https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/' -ForegroundColor DarkGray
Write-Host ''

# --------------------------------------------------------------------------
# Prompt for selection
# --------------------------------------------------------------------------
$selection = Read-Host ("Pick a model [1-{0}] (or q to quit)" -f $Models.Count)

if ($selection -eq 'q' -or $selection -eq 'Q') {
    Write-Host 'Cancelled.' -ForegroundColor Yellow
    exit 0
}

$sel = 0
if (-not [int]::TryParse($selection, [ref]$sel) -or $sel -lt 1 -or $sel -gt $Models.Count) {
    Write-Host "Invalid selection: '$selection'" -ForegroundColor Red
    exit 1
}

$chosen = $Models[$sel - 1]
Write-Host ''
Write-Host ("Selected: {0} ({1})" -f $chosen.Key, $chosen.Tier) -ForegroundColor Green
Write-Host ''

# --------------------------------------------------------------------------
# Apply: local .env
# --------------------------------------------------------------------------
function Update-EnvFile {
    param([string]$Path, [string]$Key, [string]$Value)

    $lines = @()
    $found = $false

    if (Test-Path $Path) {
        $lines = Get-Content $Path
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^\s*$Key\s*=") {
                $lines[$i] = "$Key=$Value"
                $found = $true
            }
        }
    }

    if (-not $found) { $lines += "$Key=$Value" }
    Set-Content -Path $Path -Value $lines -Encoding utf8
}

if ($Target -eq 'local' -or $Target -eq 'both') {
    Write-Host ("Updating {0}" -f $EnvFile) -ForegroundColor Cyan
    Update-EnvFile -Path $EnvFile -Key $EnvVarName -Value $chosen.Deployment
    Write-Host ("  {0}={1}" -f $EnvVarName, $chosen.Deployment) -ForegroundColor Gray
    Write-Host '  .env updated. Restart your app to pick up the change.' -ForegroundColor Green
    Write-Host ''
}

# --------------------------------------------------------------------------
# Apply: Azure Container App
# --------------------------------------------------------------------------
if ($Target -eq 'azure' -or $Target -eq 'both') {
    if (-not $ContainerApp -or -not $ResourceGroup) {
        Write-Host 'Target azure requires -ContainerApp and -ResourceGroup.' -ForegroundColor Red
        exit 1
    }

    Write-Host ("Updating Container App '{0}' in '{1}'..." -f $ContainerApp, $ResourceGroup) -ForegroundColor Cyan
    $envPair = ('{0}={1}' -f $EnvVarName, $chosen.Deployment)

    az containerapp update `
        --name $ContainerApp `
        --resource-group $ResourceGroup `
        --set-env-vars $envPair `
        --output none

    if ($LASTEXITCODE -ne 0) {
        Write-Host 'az containerapp update failed.' -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host '  Container App updated. A new revision is rolling out.' -ForegroundColor Green
    Write-Host ''
}

# --------------------------------------------------------------------------
# Reminder
# --------------------------------------------------------------------------
Write-Host 'Reminder: the deployment name above must exist in your Azure OpenAI resource.' -ForegroundColor Yellow
Write-Host 'Create it via Azure AI Foundry portal or:' -ForegroundColor Yellow
Write-Host ("  az cognitiveservices account deployment create --name <aoai-resource> --resource-group <rg> \`" ) -ForegroundColor DarkGray
Write-Host ("    --deployment-name {0} --model-name {0} --model-format OpenAI --sku-name Standard --sku-capacity 10" -f $chosen.Deployment) -ForegroundColor DarkGray
Write-Host ''
