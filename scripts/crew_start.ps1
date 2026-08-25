# crew_start.ps1 - launch one worker session for a GitHub issue.
# Creates a disposable worktree off origin/main, writes the brief from the
# template plus the issue body, and opens a Windows Terminal tab for the worker.
# The mate calls this; the maintainer may call it directly for one-off crews.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][int]$Issue,
    [ValidateSet('ship', 'scout')][string]$Autonomy = 'ship',
    # Dry-run prints the plan without touching disk.
    [switch]$WhatIfMode,
    [string]$RepoRoot
)

if (-not $RepoRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $RepoRoot = Split-Path -Parent $scriptDir
}

$ErrorActionPreference = 'Stop'
Set-Location $RepoRoot

if (-not (Test-Path (Join-Path $RepoRoot '.crew\README.md'))) {
    throw '.crew/README.md missing - crew mode conventions not installed.'
}

$issueJson = gh issue view $Issue --json title,body,url,state 2>$null
if ($LASTEXITCODE -ne 0 -or -not $issueJson) { throw "issue #$Issue not found or gh not authenticated." }
$ghIssue = $issueJson | ConvertFrom-Json
if ($ghIssue.state -ne 'OPEN') { throw "issue #$Issue is $($ghIssue.state), not OPEN." }

$slug = ($ghIssue.title.ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
if ($slug.Length -gt 30) { $slug = $slug.Substring(0, 30).Trim('-') }
$branch = "crew/$Issue-$slug"
$wtPath = Join-Path (Split-Path -Parent $RepoRoot) "IHA-$Issue"

if ($WhatIfMode) {
    Write-Output 'dry-run plan (no changes made):'
    Write-Output ("  worktree : git worktree add `"{0}`" -b {1} origin/main" -f $wtPath, $branch)
    Write-Output ("  brief    : .crew\{0}-brief.md from _brief.template.md" -f $Issue)
    Write-Output ("  terminal : wt.exe new tab at $wtPath")
    exit 0
}

if (Test-Path $wtPath) { throw "worktree path already exists: $wtPath" }
git fetch origin main | Out-Null
git worktree add $wtPath -b $branch origin/main
if ($LASTEXITCODE -ne 0) { throw 'git worktree add failed.' }

$template = Get-Content (Join-Path $RepoRoot '.crew\_brief.template.md') -Raw
$goal = ($ghIssue.body -split "`n" | Select-Object -First 25) -join "`n"
$dateUtc = '{0:u}' -f (Get-Date).ToUniversalTime()
# Ordinal literal replacements (not -replace) so issue text containing regex or
# substitution characters cannot corrupt the brief.
$pairs = [ordered]@{
    '{ISSUE_TITLE}'   = $ghIssue.title
    '{ISSUE_NUMBER}'  = "$Issue"
    '{ISSUE_URL}'     = $ghIssue.url
    '{BRANCH}'        = $branch
    '{SHIP_OR_SCOUT}' = $Autonomy.ToUpper()
    '{DATE_UTC}'      = $dateUtc
}
foreach ($key in $pairs.Keys) { $template = $template.Replace($key, [string]$pairs[$key]) }
foreach ($token in @('{GOAL', '{FILES IN SCOPE', '{EXCLUSIONS', '{VERIFICATION')) {
    $start = $template.IndexOf($token)
    if ($start -ge 0) {
        $end = $template.IndexOf('}', $start)
        if ($end -gt $start) { $template = $template.Remove($start, $end - $start + 1) }
    }
}
$briefPath = Join-Path $RepoRoot ".crew\$Issue-brief.md"
[System.IO.File]::WriteAllText($briefPath, $template, [System.Text.UTF8Encoding]::new($false))

try {
    Start-Process wt.exe -ArgumentList @('-w', '0', 'nt', '-d', "`"$wtPath`"", 'pwsh', '-NoExit',
        '-Command', "Set-Location '$wtPath'; Write-Host 'crew worker for issue #$Issue ($Autonomy) - read .crew\$Issue-brief.md'")
    $launched = $true
}
catch {
    $launched = $false
}

Write-Output "worktree   : $wtPath (branch $branch)"
Write-Output "brief      : $briefPath"
if ($launched) { Write-Output 'terminal   : new Windows Terminal tab opened' }
else { Write-Output "terminal   : wt.exe unavailable - open a terminal manually in $wtPath" }
Write-Output "next       : dispatch only if crew trigger and shared-surface lock hold (.crew/README.md)"
