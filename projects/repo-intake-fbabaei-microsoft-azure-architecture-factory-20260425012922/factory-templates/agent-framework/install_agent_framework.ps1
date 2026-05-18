[CmdletBinding()]
param(
    [string]$PythonExecutable
)

# Install the Microsoft Agent Framework SDK in the two phases required by
# the preview packaging. The azure-ai-agentserver-* packages pin
# agent-framework-core<=rc3, so the rc6 packages MUST be installed second
# so their version wins dependency resolution.
#
# This script is the canonical factory template. Projects adopting the
# Agent Framework runtime should copy it into their own scripts/ folder.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $PythonExecutable) {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $PythonExecutable = if (Test-Path $venvPython) { $venvPython } else { "python" }
}

Write-Host "Using Python: $PythonExecutable"
Write-Host ""
Write-Host "Phase 1/2: install azure-ai-agentserver stack (pins agent-framework-core<=rc3)..." -ForegroundColor Cyan
& $PythonExecutable -m pip install `
    "azure-ai-agentserver-agentframework==1.0.0b16" `
    "azure-ai-agentserver-core==1.0.0b16" `
    "agent-dev-cli==0.0.1b260316"
if ($LASTEXITCODE -ne 0) { throw "Phase 1 failed with exit code $LASTEXITCODE" }

Write-Host ""
Write-Host "Phase 2/2: upgrade agent-framework packages to rc6..." -ForegroundColor Cyan
& $PythonExecutable -m pip install --upgrade `
    "agent-framework-core==1.0.0rc6" `
    "agent-framework-foundry==1.0.0rc6" `
    "agent-framework-openai==1.0.0rc6"
if ($LASTEXITCODE -ne 0) { throw "Phase 2 failed with exit code $LASTEXITCODE" }

Write-Host ""
Write-Host "Verifying install..." -ForegroundColor Cyan
& $PythonExecutable -c "import agent_framework, agent_framework.foundry; print('agent_framework OK')"
if ($LASTEXITCODE -ne 0) { throw "Verification failed." }

Write-Host ""
Write-Host "Done. Enable the Foundry runtime with:" -ForegroundColor Green
Write-Host '  $env:AGENT_FRAMEWORK_ENABLED = "1"'
Write-Host '  $env:FOUNDRY_PROJECT_ENDPOINT = "https://<project>.services.ai.azure.com/api/projects/<project>"'
Write-Host '  $env:FOUNDRY_MODEL_DEPLOYMENT_NAME = "gpt-5.2"'
