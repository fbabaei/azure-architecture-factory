$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$indexPath = Join-Path $root '.github/agent-zone/ai-agent-index.json'
$catalogPath = Join-Path $root '.github/agent-zone/catalog.md'
$agentsPath = Join-Path $root '.github/agents'
$promptsPath = Join-Path $root '.github/prompts'
$browserPath = Join-Path $root 'browser/index.html'

if (-not (Test-Path $indexPath)) { throw "Missing registry: $indexPath" }
if (-not (Test-Path $catalogPath)) { throw "Missing catalog: $catalogPath" }
if (-not (Test-Path $agentsPath)) { throw "Missing agents folder: $agentsPath" }
if (-not (Test-Path $promptsPath)) { throw "Missing prompts folder: $promptsPath" }

$index = Get-Content $indexPath -Raw | ConvertFrom-Json
$agentFiles = @(Get-ChildItem $agentsPath -Filter '*.agent.md')
$promptFiles = @(Get-ChildItem $promptsPath -Filter '*.prompt.md')

foreach ($agent in $index.agents) {
    $agentPath = Join-Path $root $agent.path
    if (-not (Test-Path $agentPath)) {
        throw "Registry references missing agent file: $($agent.path)"
    }
}

foreach ($entryPrompt in $index.entryPrompts) {
    $promptPath = Join-Path $root $entryPrompt
    if (-not (Test-Path $promptPath)) {
        throw "Registry references missing prompt file: $entryPrompt"
    }
}

foreach ($file in @($agentFiles + $promptFiles)) {
    $lines = Get-Content $file.FullName
    $delimiters = @($lines | Select-String -Pattern '^---$')
    if ($delimiters.Count -lt 2) {
        throw "Missing YAML frontmatter delimiters: $($file.FullName)"
    }

    $frontmatter = $lines[1..($delimiters[1].LineNumber - 2)] -join "`n"
    foreach ($key in @('name:', 'description:', 'tools:')) {
        if ($frontmatter -notmatch [regex]::Escape($key)) {
            throw "Missing $key in $($file.FullName)"
        }
    }
}

foreach ($agentFile in $agentFiles) {
    $relativePath = '.github/agents/' + $agentFile.Name
    if (-not ($index.agents | Where-Object { $_.path -eq $relativePath })) {
        throw "Agent file is not registered: $relativePath"
    }
}

$catalog = Get-Content $catalogPath -Raw
if ($index.agents.id -contains 'azure-knowledge-access-architect' -and $catalog -notmatch 'Azure Knowledge Access Architect') {
    throw 'Catalog does not mention registered agent: Azure Knowledge Access Architect'
}

Write-Host "Catalog        : $($index.catalogName)"
Write-Host "Version        : $($index.version)"
Write-Host "RegistryAgents : $($index.agents.Count)"
Write-Host "AgentFiles     : $($agentFiles.Count)"
Write-Host "PromptFiles    : $($promptFiles.Count)"
Write-Host "Browser        : $(@('Missing', 'Present')[(Test-Path $browserPath)])"
Write-Host "Status         : Valid"