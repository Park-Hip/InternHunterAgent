# crew_start.ps1 - dispatch one durable crew task through Windows Terminal.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][int]$Issue,
    [ValidateSet('ship', 'scout')][string]$Autonomy = 'ship',
    # shell leaves an interactive PowerShell prompt. Any executable on PATH
    # starts as the selected harness after the worker tab opens.
    [ValidateNotNullOrEmpty()][string]$Harness = 'shell',
    # Extra arguments appended to the harness invocation. When omitted, codex
    # defaults to '--yolo'; every other harness gets no extra arguments.
    [string]$HarnessArgs,
    # wt opens a Windows Terminal tab; vscode opens the worktree in a new VS
    # Code window and auto-starts the harness in the integrated terminal panel
    # via a generated .vscode/tasks.json (requires allowing automatic tasks).
    [ValidateSet('wt', 'vscode')][string]$Backend = 'vscode',
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
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot 'crew_lifecycle.ps1')
. (Join-Path $PSScriptRoot 'crew_terminal_backend.ps1')
. (Join-Path $PSScriptRoot 'crew_vscode_backend.ps1')

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
$paths = Get-CrewTaskPaths -RepoRoot $RepoRoot -Issue $Issue
$wtPath = $paths.WorktreePath

$harnessExecutable = $null
if ($Harness -ne 'shell') {
    $harnessExecutable = Get-Command -Name $Harness -CommandType Application,ExternalScript -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $harnessExecutable) {
        throw "Harness '$Harness' is not available on PATH. Install it or use -Harness shell."
    }
}

$resolvedHarnessArgs = if (-not [string]::IsNullOrWhiteSpace($HarnessArgs)) { $HarnessArgs.Trim() }
    elseif ($Harness -eq 'codex') { '--yolo' } else { $null }

if ($WhatIfMode) {
    Write-Output 'dry-run plan (no changes made):'
    Write-Output ("  root     : {0}" -f $paths.WorktreeRoot)
    Write-Output ("  worktree : git worktree add `"{0}`" -b {1} origin/main" -f $wtPath, $branch)
    Write-Output ("  brief    : primary and task-local .crew\{0}-brief.md" -f $Issue)
    Write-Output ("  manifest : .crew\{0}-task.json" -f $Issue)
    if ($Autonomy -eq 'scout') {
        Write-Output ("  report   : {0}" -f $paths.ScoutReportPath)
    }
    if ($Backend -eq 'vscode') {
        if ($Harness -eq 'shell') {
            Write-Output ("  terminal : new VS Code window on {0} (no automatic task)" -f $wtPath)
        }
        else {
            Write-Output ("  terminal : new VS Code window on {0}; integrated-terminal task runs on folder open" -f $wtPath)
            $harnessLine = if ($resolvedHarnessArgs) { "{0} {1}" -f $harnessExecutable.Source, $resolvedHarnessArgs } else { $harnessExecutable.Source }
            Write-Output ("  harness  : {0}" -f $harnessLine)
        }
    }
    else {
        if ($Harness -eq 'shell') {
            Write-Output ("  terminal : Windows Terminal tab at {0} with an interactive PowerShell prompt" -f $wtPath)
        }
        else {
            Write-Output ("  terminal : Windows Terminal tab at {0}, then start {1}" -f $wtPath, $harnessExecutable.Source)
            if ($resolvedHarnessArgs) { Write-Output ("  harness  : {0}" -f $resolvedHarnessArgs) }
        }
    }
    exit 0
}

if (Test-Path -LiteralPath $wtPath) { throw "worktree path already exists: $wtPath" }
git fetch origin main | Out-Null
if (-not (Test-Path -LiteralPath $paths.WorktreeRoot)) {
    New-Item -ItemType Directory -Path $paths.WorktreeRoot -Force | Out-Null
}
git worktree add $wtPath -b $branch origin/main
if ($LASTEXITCODE -ne 0) { throw 'git worktree add failed.' }

$template = Get-Content (Join-Path $RepoRoot '.crew\_brief.template.md') -Raw
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
    '{PRIMARY_REPO}'  = $RepoRoot
    '{TASK_MANIFEST}' = $paths.TaskManifestPath
    '{PRIMARY_STATUS}' = $paths.PrimaryStatusPath
    '{SCOUT_REPORT}'  = if ($Autonomy -eq 'scout') { $paths.ScoutReportPath } else { 'Not applicable for ship tasks.' }
}
foreach ($key in $pairs.Keys) { $template = $template.Replace($key, [string]$pairs[$key]) }
foreach ($token in @('{GOAL', '{FILES IN SCOPE', '{EXCLUSIONS', '{VERIFICATION')) {
    $start = $template.IndexOf($token)
    if ($start -ge 0) {
        $end = $template.IndexOf('}', $start)
        if ($end -gt $start) { $template = $template.Remove($start, $end - $start + 1) }
    }
}
Write-CrewUtf8File -Path $paths.PrimaryBriefPath -Content $template
Write-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Issue $Issue -IssueUrl $ghIssue.url `
    -Title $ghIssue.title -Autonomy $Autonomy -Branch $branch -RepoRoot $RepoRoot -WorktreePath $wtPath `
    -PrimaryBriefPath $paths.PrimaryBriefPath -PrimaryStatusPath $paths.PrimaryStatusPath `
    -TaskBriefPath $paths.TaskBriefPath -ScoutReportPath $paths.ScoutReportPath -TerminalBackend $Backend | Out-Null
Copy-CrewTaskContractFiles -PrimaryBriefPath $paths.PrimaryBriefPath -TaskBriefPath $paths.TaskBriefPath `
    -PrimaryManifestPath $paths.PrimaryManifestPath -TaskManifestPath $paths.TaskManifestPath

$escapedWorktreePath = $wtPath.Replace("'", "''")
$workerMessage = "crew worker for issue #$Issue ($Autonomy) - read .crew\$Issue-brief.md"
$sessionCommand = "Set-Location -LiteralPath '$escapedWorktreePath'; Write-Host '$workerMessage'"
if ($Harness -ne 'shell') {
    $escapedHarnessPath = $harnessExecutable.Source.Replace("'", "''")
    $sessionCommand += "; & '$escapedHarnessPath'"
    if ($resolvedHarnessArgs) {
        foreach ($arg in ($resolvedHarnessArgs -split '\s+')) {
            $sessionCommand += " '$($arg.Replace("'", "''"))'"
        }
    }
}
if ($Backend -eq 'vscode') {
    $taskName = "IHA-$Issue worker"
    $launchPlan = New-CrewVsCodeLaunchPlan -WorktreePath $wtPath -SessionCommand $sessionCommand -TaskName $taskName
    if ($launchPlan -and $Harness -ne 'shell') {
        Write-CrewVsCodeTerminalTask -WorktreePath $wtPath -TaskName $taskName -SessionCommand $sessionCommand
    }
    $launchResult = if ($launchPlan) { Start-CrewVsCode -LaunchPlan $launchPlan }
                    else { [pscustomobject]@{ Launched = $false; Detail = 'code CLI unavailable on PATH' } }
}
else {
    $launchPlan = New-CrewWindowsTerminalLaunchPlan -WorktreePath $wtPath -SessionCommand $sessionCommand
    $launchResult = Start-CrewWindowsTerminal -LaunchPlan $launchPlan
}
Update-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Changes @{
    TerminalLaunchStatus = if ($launchResult.Launched) { 'launched' } else { 'unavailable' }
    TerminalLaunchDetail = $launchResult.Detail
} | Out-Null

Write-Output "worktree   : $wtPath (branch $branch)"
Write-Output "brief      : $($paths.PrimaryBriefPath)"
Write-Output "manifest   : $($paths.PrimaryManifestPath)"
if ($Backend -eq 'vscode') {
    if ($launchResult.Launched -and $Harness -eq 'shell') { Write-Output 'terminal   : new VS Code window opened on the worktree (open a terminal manually for a harness)' }
    elseif ($launchResult.Launched) { Write-Output "terminal   : new VS Code window opened; allow automatic tasks so the integrated-terminal task starts $Harness$(if ($resolvedHarnessArgs) { " $($resolvedHarnessArgs)" })" }
    else { Write-Output "terminal   : $($launchResult.Detail) - run 'code -n $wtPath' manually" }
}
if ($launchResult.Launched -and $Harness -eq 'shell') { Write-Output 'terminal   : new Windows Terminal tab opened with an interactive PowerShell prompt' }
elseif ($launchResult.Launched) { Write-Output "terminal   : new Windows Terminal tab opened with interactive $Harness session" }
else { Write-Output "terminal   : $($launchResult.Detail) - open a terminal manually in $wtPath" }
Write-Output "next       : dispatch only if crew trigger and shared-surface lock hold (.crew/README.md)"
