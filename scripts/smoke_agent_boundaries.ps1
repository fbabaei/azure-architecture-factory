param([string]$Root = ".github/agents")

$fail = 0
function Check([string]$label, [bool]$ok) {
  $mark = if ($ok) { "PASS" } else { $script:fail++; "FAIL" }
  "{0,-6} {1}" -f $mark, $label
}

Write-Host "=== 1. Owns/Does Not Own coverage ===" -ForegroundColor Cyan
$agents = @(
  "azure-architecture-implementer",
  "source-code-maintainer",
  "bicep-infrastructure-validator",
  "production-environment-advisor",
  "security-compliance-auditor"
)
foreach ($n in $agents) {
  $c = Get-Content "$Root/$n.agent.md" -Raw
  $owns = ([regex]::Matches($c, '(?m)^##\s+Owns')).Count
  $hasNot = $c -match 'Does\s+NOT\s+own|Does\s+Not\s+Own'
  Check "$n has exactly 1 Owns section"  ($owns -eq 1)
  Check "$n declares Does Not Own"       $hasNot
}

Write-Host "`n=== 2. Phase 2.6 Security Gate wiring ===" -ForegroundColor Cyan
$orch = Get-Content "$Root/project-orchestrator.agent.md" -Raw
Check "Phase 2.6 section present"    ($orch -match 'Phase 2\.6 . Security')
Check "Manifest key 2_6_security_gate" ($orch -match '2_6_security_gate')
Check "Orchestration row 2.6"        ($orch -match '2\.6 . Security . Compliance')
Check "skip-security bypass"         ($orch -match 'skip-security')
Check "security-compliance-auditor in agents frontmatter" ($orch -match 'agents:.*security-compliance-auditor')
Check "Constraints mention 2.6"      ($orch -match 'Phase 2\.6 \(Security')

Write-Host "`n=== 3. Maintainer rename ===" -ForegroundColor Cyan
$mnt = Get-Content "$Root/source-code-maintainer.agent.md" -Raw
Check "add-to-service mode defined"  ($mnt -match 'add-to-service')
Check "no stale 'generate' mode row" (-not ($mnt -match '(?m)^\|\s*`?generate`?\s*\|'))
Check "argument-hint uses add-to-service" ($mnt -match 'argument-hint:.*add-to-service')
Check "argument-hint no longer says generate|" (-not ($mnt -match 'argument-hint:.*\bgenerate\|'))

Write-Host "`n=== 4. README sync ===" -ForegroundColor Cyan
$rm = Get-Content "$Root/README.md" -Raw
Check "five gates narrative"         ($rm -match 'five.*non-optional')
Check "Phase 2.6 line in tree"       ($rm -match '\[Phase 2\.6\]')
Check "auditor in tree"              ($rm -match 'security-compliance-auditor')
Check "add-to-service in tree"       ($rm -match 'add-to-service')
Check "no stale 'generate, refactor' mode list" (-not ($rm -match 'generate, refactor'))

Write-Host "`n=== 5. Contention probe (positive-claim uniqueness) ===" -ForegroundColor Cyan
# For each domain phrase, extract the "**Owns:**" block of each agent and check which agents claim it positively.
function Get-OwnsBlock($path) {
  $txt = Get-Content $path -Raw
  # Bold form: **Owns:** ... **Does NOT own**
  $m = [regex]::Match($txt, '(?s)\*\*Owns[^*]*\*\*(.*?)\*\*Does\s+(NOT|Not)\s+[Oo]wn')
  if ($m.Success) { return $m.Groups[1].Value }
  # Heading form: ## Owns ... ## Does Not Own
  $m = [regex]::Match($txt, '(?s)(?m)^##\s+Owns\s*$(.*?)^##\s+Does\s+Not\s+Own')
  if ($m.Success) { return $m.Groups[1].Value }
  return ""
}

$probes = @(
  @{ Phrase = "scaffold";                ExpectedAgents = @("azure-architecture-implementer") },
  @{ Phrase = "Bicep / ``.bicepparam``"; ExpectedAgents = @("bicep-infrastructure-validator") },
  @{ Phrase = "Secret-management audit"; ExpectedAgents = @("security-compliance-auditor") },
  @{ Phrase = "drift";                   ExpectedAgents = @("source-code-maintainer") },
  @{ Phrase = "prerequisite";            ExpectedAgents = @("production-environment-advisor") }
)

foreach ($p in $probes) {
  $claimers = @()
  foreach ($n in $agents) {
    $owns = Get-OwnsBlock "$Root/$n.agent.md"
    if ($owns -match [regex]::Escape($p.Phrase)) { $claimers += $n }
  }
  $ok = ($claimers.Count -gt 0) -and (($claimers | Where-Object { $_ -notin $p.ExpectedAgents }).Count -eq 0)
  Check ("'{0}' positively claimed by: {1} (expected: {2})" -f $p.Phrase, ($claimers -join ','), ($p.ExpectedAgents -join ',')) $ok
}

Write-Host ""
if ($fail -eq 0) {
  Write-Host "ALL CHECKS PASSED" -ForegroundColor Green
  exit 0
} else {
  Write-Host "$fail CHECK(S) FAILED" -ForegroundColor Red
  exit 1
}
