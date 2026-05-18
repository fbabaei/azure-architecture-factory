[CmdletBinding()]
param(
    [string]$ResourceGroupName,
    [string]$DeploymentName,
    [string]$SearchEndpoint,
    [string]$OpenAIEndpoint,
    [string]$IndexName = "compliance-knowledge-base",
    [string]$EmbeddingsDeployment = "text-embedding-3-small",
    [string]$SourceDir,
    [string]$ManifestPath,
    [string]$PythonExecutable,
    [switch]$CreateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$bootstrapScript = Join-Path $PSScriptRoot "bootstrap_search_index.py"

if (-not $SourceDir) {
    $SourceDir = Join-Path $projectRoot "sample-corpus"
}
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $SourceDir "manifest.json"
}
if (-not $PythonExecutable) {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $PythonExecutable = if (Test-Path $venvPython) { $venvPython } else { "python" }
}

function Resolve-LatestDeploymentName {
    param([Parameter(Mandatory = $true)][string]$ResourceGroup)

    $name = az deployment group list `
        --resource-group $ResourceGroup `
        --query "sort_by([?properties.provisioningState=='Succeeded'], &properties.timestamp)[-1].name" `
        -o tsv

    if (-not $name) {
        throw "No successful group deployment found for resource group '$ResourceGroup'."
    }

    return $name.Trim()
}

function Get-DeploymentOutputs {
    param(
        [Parameter(Mandatory = $true)][string]$ResourceGroup,
        [Parameter(Mandatory = $true)][string]$Deployment
    )

    $json = az deployment group show `
        --resource-group $ResourceGroup `
        --name $Deployment `
        --query properties.outputs `
        -o json

    if (-not $json) {
        throw "Deployment '$Deployment' did not return outputs."
    }

    return $json | ConvertFrom-Json
}

if ((-not $SearchEndpoint -or -not $OpenAIEndpoint) -and -not $ResourceGroupName) {
    throw "Provide -ResourceGroupName so the script can resolve deployment outputs, or pass both -SearchEndpoint and -OpenAIEndpoint explicitly."
}

if (-not $SearchEndpoint -or -not $OpenAIEndpoint) {
    if (-not $DeploymentName) {
        $DeploymentName = Resolve-LatestDeploymentName -ResourceGroup $ResourceGroupName
    }
    $outputs = Get-DeploymentOutputs -ResourceGroup $ResourceGroupName -Deployment $DeploymentName
    if (-not $SearchEndpoint) {
        $SearchEndpoint = $outputs.aiSearchEndpoint.value
    }
    if (-not $OpenAIEndpoint) {
        $OpenAIEndpoint = $outputs.openAiEndpoint.value
    }
}

if (-not $SearchEndpoint) {
    throw "Unable to resolve Azure AI Search endpoint."
}
if (-not $OpenAIEndpoint -and -not $CreateOnly) {
    throw "Unable to resolve Azure OpenAI endpoint."
}

$arguments = @(
    $bootstrapScript,
    "--search-endpoint", $SearchEndpoint,
    "--index-name", $IndexName,
    "--embeddings-deployment", $EmbeddingsDeployment
)

if (-not $CreateOnly) {
    $arguments += @("--openai-endpoint", $OpenAIEndpoint)
}
if (Test-Path $ManifestPath) {
    $arguments += @("--manifest", $ManifestPath)
} elseif (Test-Path $SourceDir) {
    $arguments += @("--source-dir", $SourceDir)
}
if ($CreateOnly) {
    $arguments += "--create-only"
}

Write-Host "Using search endpoint: $SearchEndpoint"
if (-not $CreateOnly) {
    Write-Host "Using OpenAI endpoint: $OpenAIEndpoint"
}
if ($DeploymentName) {
    Write-Host "Deployment outputs source: $DeploymentName"
}

& $PythonExecutable @arguments
exit $LASTEXITCODE