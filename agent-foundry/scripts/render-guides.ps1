$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

$guides = @(
    @{
        Source = Join-Path $repoRoot "docs/application-implementation-step-by-step.md"
        Output = Join-Path $repoRoot "docs/application-implementation-step-by-step.html"
        Title = "Azure AI Agent Foundry Application Implementation"
    },
    @{
        Source = Join-Path $repoRoot "docs/learning-paths-step-by-step.md"
        Output = Join-Path $repoRoot "docs/learning-paths-step-by-step.html"
        Title = "Azure AI Agent Foundry Learning Paths"
    },
    @{
      Source = Join-Path $repoRoot "docs/azure-ai-search-agents-step-by-step.md"
      Output = Join-Path $repoRoot "docs/azure-ai-search-agents-step-by-step.html"
      Title = "Azure AI Agent Foundry Azure AI Search Agents"
    },
    @{
      Source = Join-Path $repoRoot "docs/reconfigurable-agents.md"
      Output = Join-Path $repoRoot "docs/reconfigurable-agents.html"
      Title = "Azure AI Agent Foundry Reconfigurable Agents"
    },
    @{
      Source = Join-Path $repoRoot "docs/reconfigurable-agents-quick-start.md"
      Output = Join-Path $repoRoot "docs/reconfigurable-agents-quick-start.html"
      Title = "Azure AI Agent Foundry Reconfigurable Agents Quick Start"
    },
    @{
      Source = Join-Path $repoRoot "docs/reconfigurable-agents-walkthrough.md"
      Output = Join-Path $repoRoot "docs/reconfigurable-agents-walkthrough.html"
      Title = "Azure AI Agent Foundry Reconfigurable Agents Walkthrough"
    },
    @{
      Source = Join-Path $repoRoot "docs/document-intelligence-agents-step-by-step.md"
      Output = Join-Path $repoRoot "docs/document-intelligence-agents-step-by-step.html"
      Title = "Azure AI Agent Foundry Document Intelligence Agents"
    },
    @{
      Source = Join-Path $repoRoot "docs/prompt-files-guide.md"
      Output = Join-Path $repoRoot "docs/prompt-files-guide.html"
      Title = "Azure AI Agent Foundry Prompt Files Guide"
    }
)

foreach ($guide in $guides) {
    if (-not (Test-Path $guide.Source)) {
        throw "Guide source not found: $($guide.Source)"
    }

    $markdown = Get-Content -Raw -Path $guide.Source
    $body = (ConvertFrom-Markdown -InputObject $markdown).Html
    $sourceName = Split-Path -Leaf $guide.Source

    $page = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$($guide.Title)</title>
  <script>
    (() => {
      const param = new URLSearchParams(window.location.search).get("scoutTheme");
      const theme =
        param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", theme);
    })();
  </script>
  <style>
    :root {
      color-scheme: light;
      --cp-bg: #f7f4ef;
      --cp-bg-elevated: #fcfbf8;
      --cp-surface: #ffffff;
      --cp-surface-soft: #f5f5f5;
      --cp-border: #dedede;
      --cp-border-strong: #919191;
      --cp-text: #242424;
      --cp-text-muted: #5c5c5c;
      --cp-text-soft: #6f6f6f;
      --cp-accent: #b11f4b;
      --cp-accent-hover: #9a1a41;
      --cp-accent-soft: rgba(177, 31, 75, 0.08);
      --cp-accent-fg: #ffffff;
      --cp-success: #16a34a;
      --cp-danger: #dc2626;
      --cp-warning: #f59e0b;
      --cp-link: #0078d4;
      --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
      --cp-overlay: rgba(255, 255, 255, 0.8);
      --cp-panel: rgba(255, 255, 255, 0.86);
      --cp-panel-strong: rgba(255, 255, 255, 0.96);
      --cp-sheen: rgba(255, 255, 255, 0.55);
      --cp-highlight: rgba(177, 31, 75, 0.12);
    }
    html[data-theme="dark"] {
      color-scheme: dark;
      --cp-bg: #3d3b3a;
      --cp-bg-elevated: #343231;
      --cp-surface: #292929;
      --cp-surface-soft: #2e2e2e;
      --cp-border: #474747;
      --cp-border-strong: #5f5f5f;
      --cp-text: #dedede;
      --cp-text-muted: #919191;
      --cp-text-soft: #b0b0b0;
      --cp-accent: #fd8ea1;
      --cp-accent-hover: #fb7b91;
      --cp-accent-soft: rgba(253, 142, 161, 0.14);
      --cp-accent-fg: #1a1a1a;
      --cp-success: #4ade80;
      --cp-danger: #f87171;
      --cp-warning: #fbbf24;
      --cp-link: #4da6ff;
      --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
      --cp-overlay: rgba(41, 41, 41, 0.88);
      --cp-panel: rgba(41, 41, 41, 0.72);
      --cp-panel-strong: rgba(41, 41, 41, 0.96);
      --cp-sheen: rgba(255, 255, 255, 0.04);
      --cp-highlight: rgba(253, 142, 161, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--cp-bg);
      color: var(--cp-text);
      font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    a { color: var(--cp-link); }
    .shell { max-width: 1040px; margin: 0 auto; padding: 32px; }
    .guide {
      background: var(--cp-surface);
      border: 1px solid var(--cp-border);
      border-radius: 16px;
      box-shadow: 0 0 2px var(--cp-border), 0 1px 2px var(--cp-border);
      padding: 32px;
    }
    .source-link { margin-bottom: 24px; color: var(--cp-text-soft); }
    h1, h2, h3 { color: var(--cp-text); letter-spacing: 0; }
    h1 { margin: 0 0 16px; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1; }
    h2 { margin-top: 36px; padding-top: 20px; border-top: 1px solid var(--cp-border); }
    h3 { margin-top: 28px; }
    p, li { color: var(--cp-text-muted); line-height: 1.6; }
    table { width: 100%; border-collapse: collapse; margin: 18px 0; overflow: auto; display: block; }
    th, td { border: 1px solid var(--cp-border); padding: 10px 12px; text-align: left; vertical-align: top; }
    th { background: var(--cp-surface-soft); color: var(--cp-text); }
    code { font-family: Consolas, "Courier New", Courier, monospace; color: var(--cp-text); }
    pre {
      background: var(--cp-bg-elevated);
      border: 1px solid var(--cp-border);
      border-radius: 0.625rem;
      color: var(--cp-text);
      overflow: auto;
      padding: 14px;
    }
    @media (max-width: 720px) {
      .shell { padding: 16px; }
      .guide { padding: 20px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <article class="guide">
      <p class="source-link">Rendered from <a href="$sourceName">$sourceName</a></p>
$body
    </article>
  </main>
</body>
</html>
"@

    Set-Content -Path $guide.Output -Value $page -Encoding utf8
    Write-Host "Rendered $($guide.Output)"
}

$promptOutputRoot = Join-Path $repoRoot "docs/prompts"
New-Item -ItemType Directory -Path $promptOutputRoot -Force | Out-Null

Get-ChildItem -Path (Join-Path $repoRoot ".github/prompts") -Filter "*.prompt.md" | ForEach-Object {
    $raw = Get-Content -Raw -Path $_.FullName
    $frontmatter = @{}
    $bodyMarkdown = $raw

    if ($raw -match '(?s)^---\r?\n(?<frontmatter>.*?)\r?\n---\r?\n(?<body>.*)$') {
        $bodyMarkdown = $Matches.body.Trim()
        foreach ($line in ($Matches.frontmatter -split "\r?\n")) {
            if ($line -match '^([^:]+):\s*(.*)$') {
                $key = $Matches[1].Trim()
                $value = $Matches[2].Trim().Trim('"')
                $frontmatter[$key] = $value
            }
        }
    }

    $name = if ($frontmatter.ContainsKey("name")) { $frontmatter["name"] } else { $_.BaseName }
    $description = if ($frontmatter.ContainsKey("description")) { $frontmatter["description"] } else { "Prompt entry point." }
    $agent = if ($frontmatter.ContainsKey("agent")) { $frontmatter["agent"] } else { "Unspecified" }
    $tools = if ($frontmatter.ContainsKey("tools")) { $frontmatter["tools"] } else { "Unspecified" }
    $argumentHint = if ($frontmatter.ContainsKey("argument-hint")) { $frontmatter["argument-hint"] } else { "None" }
    $sourceName = $_.Name
    $slug = $_.Name -replace '\.prompt\.md$', ''
    $output = Join-Path $promptOutputRoot "$slug.html"

    $promptMarkdown = @"
# $name

$description

| Field | Value |
| --- | --- |
| Slash command | `/$slug` |
| Routes to | $agent |
| Tools | `$tools` |
| Argument hint | $argumentHint |
| Source file | `.github/prompts/$sourceName` |

## Prompt Instructions

$bodyMarkdown
"@

    $body = (ConvertFrom-Markdown -InputObject $promptMarkdown).Html

    $page = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$name</title>
  <script>
    (() => {
      const param = new URLSearchParams(window.location.search).get("scoutTheme");
      const theme =
        param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", theme);
    })();
  </script>
  <style>
    :root {
      color-scheme: light;
      --cp-bg: #f7f4ef;
      --cp-bg-elevated: #fcfbf8;
      --cp-surface: #ffffff;
      --cp-surface-soft: #f5f5f5;
      --cp-border: #dedede;
      --cp-border-strong: #919191;
      --cp-text: #242424;
      --cp-text-muted: #5c5c5c;
      --cp-text-soft: #6f6f6f;
      --cp-accent: #b11f4b;
      --cp-link: #0078d4;
    }
    html[data-theme="dark"] {
      color-scheme: dark;
      --cp-bg: #3d3b3a;
      --cp-bg-elevated: #343231;
      --cp-surface: #292929;
      --cp-surface-soft: #2e2e2e;
      --cp-border: #474747;
      --cp-border-strong: #5f5f5f;
      --cp-text: #dedede;
      --cp-text-muted: #919191;
      --cp-text-soft: #b0b0b0;
      --cp-accent: #fd8ea1;
      --cp-link: #4da6ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--cp-bg);
      color: var(--cp-text);
      font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    a { color: var(--cp-link); }
    .shell { max-width: 1040px; margin: 0 auto; padding: 32px; }
    .guide {
      background: var(--cp-surface);
      border: 1px solid var(--cp-border);
      border-radius: 16px;
      box-shadow: 0 0 2px var(--cp-border), 0 1px 2px var(--cp-border);
      padding: 32px;
    }
    .source-link { margin-bottom: 24px; color: var(--cp-text-soft); }
    h1, h2, h3 { color: var(--cp-text); letter-spacing: 0; }
    h1 { margin: 0 0 16px; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1; }
    h2 { margin-top: 36px; padding-top: 20px; border-top: 1px solid var(--cp-border); }
    p, li { color: var(--cp-text-muted); line-height: 1.6; }
    table { width: 100%; border-collapse: collapse; margin: 18px 0; overflow: auto; display: block; }
    th, td { border: 1px solid var(--cp-border); padding: 10px 12px; text-align: left; vertical-align: top; }
    th { background: var(--cp-surface-soft); color: var(--cp-text); }
    code { font-family: Consolas, "Courier New", Courier, monospace; color: var(--cp-text); }
    pre {
      background: var(--cp-bg-elevated);
      border: 1px solid var(--cp-border);
      border-radius: 0.625rem;
      color: var(--cp-text);
      overflow: auto;
      padding: 14px;
    }
    @media (max-width: 720px) {
      .shell { padding: 16px; }
      .guide { padding: 20px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <article class="guide">
      <p class="source-link">Rendered from <a href="../../.github/prompts/$sourceName">$sourceName</a></p>
$body
    </article>
  </main>
</body>
</html>
"@

    Set-Content -Path $output -Value $page -Encoding utf8
    Write-Host "Rendered $output"
}