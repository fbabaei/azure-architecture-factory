$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$indexPath = Join-Path $root ".github/agent-zone/ai-agent-index.json"
$catalogPath = Join-Path $root ".github/agent-zone/catalog.md"
$agentsPath = Join-Path $root ".github/agents"
$promptsPath = Join-Path $root ".github/prompts"
$browserPath = Join-Path $root "browser/index.html"

if (-not (Test-Path $indexPath)) {
    throw "Missing registry: $indexPath"
}

if (-not (Test-Path $catalogPath)) {
    throw "Missing catalog: $catalogPath"
}

if (-not (Test-Path $browserPath)) {
    throw "Missing AAF browser: $browserPath"
}

$index = Get-Content $indexPath -Raw | ConvertFrom-Json
$browserContent = Get-Content $browserPath -Raw
$agentFiles = @(Get-ChildItem $agentsPath -Filter "*.agent.md" -File)
$promptFiles = @(Get-ChildItem $promptsPath -Filter "*.prompt.md" -File)

$externalPath = Join-Path $root "external"
if (Test-Path $externalPath) {
    $missingSourceRepos = @($index.sourceRepositories | Where-Object { -not (Test-Path (Join-Path $root $_.localPath)) })
    if ($missingSourceRepos.Count -gt 0) {
        $missingSourceRepos | Select-Object name,localPath | Format-Table -AutoSize
        throw "Missing source repositories. Re-clone external dependencies."
    }

    $missingSourcePaths = @()
    foreach ($agent in $index.agents) {
        if ($agent.PSObject.Properties.Name -contains "sourcePaths") {
            foreach ($sourcePath in $agent.sourcePaths) {
                if (-not (Test-Path (Join-Path $root $sourcePath))) {
                    $missingSourcePaths += [pscustomobject]@{
                        id = $agent.id
                        sourcePath = $sourcePath
                    }
                }
            }
        }
    }

    if ($missingSourcePaths.Count -gt 0) {
        $missingSourcePaths | Format-Table -AutoSize
        throw "Registry contains missing source paths."
    }
} else {
    Write-Warning "Skipping source repository validation because external/ is not packaged in this portal copy."
}

$missingAgentPaths = @($index.agents | Where-Object { -not (Test-Path (Join-Path $root $_.path)) })
if ($missingAgentPaths.Count -gt 0) {
    $missingAgentPaths | Select-Object id,path | Format-Table -AutoSize
    throw "Registry contains missing agent paths."
}

$registryPathSet = @{}
foreach ($agent in $index.agents) {
    $registryPathSet[$agent.path] = $true
}

$unregisteredAgents = @($agentFiles | Where-Object {
    $relative = $_.FullName.Substring($root.Length + 1).Replace("\", "/")
    -not $registryPathSet.ContainsKey($relative)
})
if ($unregisteredAgents.Count -gt 0) {
    $unregisteredAgents | Select-Object Name,FullName | Format-Table -AutoSize
    throw "Found agent files missing from registry."
}

function Test-Frontmatter {
    param(
        [Parameter(Mandatory=$true)] [System.IO.FileInfo] $File,
        [Parameter(Mandatory=$true)] [string[]] $RequiredKeys
    )

    $content = Get-Content $File.FullName -Raw
    if ($content -notmatch "(?s)^---\s*(.*?)\s*---") {
        throw "Missing YAML frontmatter: $($File.FullName)"
    }

    $frontmatter = $Matches[1]
    foreach ($key in $RequiredKeys) {
        if ($frontmatter -notmatch "(?m)^$([regex]::Escape($key))\s*:") {
            throw "Missing frontmatter key '$key': $($File.FullName)"
        }
    }
}

foreach ($file in $agentFiles) {
    Test-Frontmatter -File $file -RequiredKeys @("name", "description")
}

foreach ($file in $promptFiles) {
    Test-Frontmatter -File $file -RequiredKeys @("name", "description", "agent")
}

$missingBrowserAgents = @($index.agents | Where-Object { $browserContent -notmatch [regex]::Escape($_.id) })
if ($missingBrowserAgents.Count -gt 0) {
    $missingBrowserAgents | Select-Object id,path | Format-Table -AutoSize
    throw "AAF browser is missing one or more registered agent IDs."
}

[pscustomobject]@{
    Catalog = $index.catalogName
    Version = $index.version
    RegistryAgents = $index.agents.Count
    AgentFiles = $agentFiles.Count
    PromptFiles = $promptFiles.Count
    Browser = "Present"
    Status = "Valid"
}
