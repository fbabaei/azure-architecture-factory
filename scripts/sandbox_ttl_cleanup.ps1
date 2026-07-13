<#
.SYNOPSIS
    TTL reaper for the Architecture Factory sandbox resource group.

.DESCRIPTION
    Deletes resources in the sandbox resource group whose `expiresOn` tag is in
    the past. Run on a schedule (e.g. a Container Apps cron job or Azure
    Automation) to enforce the sandbox's hard cost/lifecycle boundary.

    The `expiresOn` tag is required by the sandbox 'require expiresOn tag' policy,
    so every resource the generation job creates should carry it. Set it to an
    ISO-8601 UTC timestamp, e.g. 2026-07-15T00:00:00Z.

.EXAMPLE
    pwsh -File scripts/sandbox_ttl_cleanup.ps1 -WhatIf
    pwsh -File scripts/sandbox_ttl_cleanup.ps1 -ResourceGroup arch-factory-sandbox-rg
#>
param(
    [string]$ResourceGroup = 'arch-factory-sandbox-rg',
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$now = (Get-Date).ToUniversalTime()

Write-Output "Sandbox TTL cleanup — RG: $ResourceGroup — now (UTC): $($now.ToString('o'))"

$json = az resource list --resource-group $ResourceGroup --query "[?tags.expiresOn!=null].{id:id,name:name,type:type,expiresOn:tags.expiresOn}" -o json
$resources = if ($json) { $json | ConvertFrom-Json } else { @() }

if (-not $resources -or $resources.Count -eq 0) {
    Write-Output 'No resources with an expiresOn tag found.'
    return
}

$expiredCount = 0
foreach ($r in $resources) {
    $exp = [datetime]::MinValue
    $parsed = [datetime]::TryParse($r.expiresOn, [ref]$exp)
    if (-not $parsed) {
        Write-Warning "Skipping $($r.name): unparseable expiresOn '$($r.expiresOn)'"
        continue
    }
    if ($exp.ToUniversalTime() -lt $now) {
        $expiredCount++
        if ($WhatIf) {
            Write-Output "WOULD DELETE: $($r.name) [$($r.type)] (expired $($r.expiresOn))"
        }
        else {
            Write-Output "Deleting: $($r.name) [$($r.type)] (expired $($r.expiresOn))"
            az resource delete --ids $r.id | Out-Null
        }
    }
}

Write-Output "Done. Expired resources $(if ($WhatIf) { 'that would be deleted' } else { 'deleted' }): $expiredCount"
