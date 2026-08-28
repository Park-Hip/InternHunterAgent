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
    # via a generated .vscode/tasks.json (requires allowing automatic tasks);
    # vscode-task registers a "Crew: IHA-<issue> worker" task in THIS checkout's
    # .vscode/tasks.json without launching anything - start it from the terminal
    # panel of an already-running window via Terminal > Run Task.
    [ValidateSet('wt', 'vscode', 'vscode-task')][string]$Backend = 'vscode',
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

# The harness receives the brief as its initial prompt argument so it starts
# working without a human typing anything. Wording is autonomy-aware: scouts
# write reports, ships open pull requests.
$workerPrompt = if ($Autonomy -eq 'scout') {
        "Read the file .crew/$Issue-brief.md in this repository and execute exactly what it specifies as a scout: investigate only, never push, and write your durable report to the report path given in the brief. Record progress lines in the primary status path given in the brief."
    }
    else {
        "Read the file .crew/$Issue-brief.md in this repository and execute the task it describes end to end: implement the changes it specifies in this worktree, run the verification commands it lists, then open the pull request with gh as instructed. Record progress lines in the primary status path given in the brief."
    }

if ($WhatIfMode) {
    Write-Output 'dry-run plan (no changes made):'
    Write-Output ("  root     : {0}" -f $paths.WorktreeRoot)
    Write-Output ("  worktree : git worktree add `"{0}`" -b {1} origin/main" -f $wtPath, $branch)
    Write-Output ("  brief    : primary and task-local .crew\{0}-brief.md" -f $Issue)
    Write-Output ("  manifest : .crew\{0}-task.json" -f $Issue)
    if ($Autonomy -eq 'scout') {
        Write-Output ("  report   : {0}" -f $paths.ScoutReportPath)
    }
    if ($Backend -eq 'vscode-task') {
        Write-Output ("  task     : register 'Crew: IHA-{0} worker ({1})' in this checkout's .vscode/tasks.json (cwd = worktree, harness gets the brief as its initial prompt)" -f $Issue, $Harness)
        Write-Output '  start    : Ctrl+Shift+P > Tasks: Run Task > the registered worker task'
    }
    elseif ($Backend -eq 'vscode') {
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

if ($Backend -eq 'vscode-task' -and $Harness -eq 'shell') {
    throw '-Backend vscode-task starts the worker from your terminal panel and requires -Harness <executable>.'
}
# Relaunch of an existing dispatched task: reuse its worktree, brief, and
# manifest; only (re-)register the terminal-panel task entry.
if ($Backend -eq 'vscode-task' -and (Test-Path -LiteralPath $wtPath)) {
    if (-not (Test-Path -LiteralPath $paths.PrimaryManifestPath)) {
        throw "worktree exists at '$wtPath' without a task manifest; cannot relaunch."
    }
    $taskName = "Crew: IHA-$Issue worker ($Harness)"
    Add-CrewVsCodeTaskEntry -RepoRoot $RepoRoot -WorktreePath $wtPath -TaskName $taskName `
        -HarnessPath $harnessExecutable.Source -HarnessArgs $(if ($resolvedHarnessArgs) { $resolvedHarnessArgs } else { '' }) `
        -WorkerPrompt $workerPrompt | Out-Null
    Update-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Changes @{
        State                = 'dispatched'
        TerminalBackend      = 'vscode-task'
        TerminalLaunchStatus = 'awaiting-task-run'
        TerminalLaunchDetail = "registered '$taskName' in .vscode/tasks.json (cwd = worktree, harness gets the brief as initial prompt); start via Terminal > Run Task"
    } | Out-Null
    Write-Output "relaunch   : reused worktree $wtPath"
    Write-Output "task       : '$taskName' registered in .vscode/tasks.json"
    Write-Output "next       : Ctrl+Shift+P > Tasks: Run Task > '$taskName' - it starts in this window's terminal panel"
    exit 0
}
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
foreach ($token in @(
    '{GOAL', '{DURABLE_RESEARCH_OR_APPROVED_PLAN_PATH', '{STABLE_HEADING',
    '{GAP_OR_FINDING_ID', '{CONCISE_EVIDENCE_BACKED_REASON_FOR_THIS_TASK}',
    '{FILES IN SCOPE', '{EXCLUSIONS', '{VERIFICATION'
)) {
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
$escapedPrompt = $workerPrompt.Replace("'", "''")
$workerMessage = "crew worker for issue #$Issue ($Autonomy) - the brief is passed to the harness as its initial prompt"
$sessionCommand = "Set-Location -LiteralPath '$escapedWorktreePath'; Write-Host '$workerMessage'"
if ($Harness -ne 'shell') {
    $escapedHarnessPath = $harnessExecutable.Source.Replace("'", "''")
    $sessionCommand += "; & '$escapedHarnessPath'"
    if ($resolvedHarnessArgs) {
        foreach ($arg in ($resolvedHarnessArgs -split '\s+')) {
            $sessionCommand += " '$($arg.Replace("'", "''"))'"
        }
    }
    # The brief as initial prompt - the harness starts working immediately.
    $sessionCommand += " '$escapedPrompt'"
}
if ($Backend -eq 'vscode-task') {
    $taskName = "Crew: IHA-$Issue worker ($Harness)"
    Add-CrewVsCodeTaskEntry -RepoRoot $RepoRoot -WorktreePath $wtPath -TaskName $taskName `
        -HarnessPath $harnessExecutable.Source -HarnessArgs $(if ($resolvedHarnessArgs) { $resolvedHarnessArgs } else { '' }) `
        -WorkerPrompt $workerPrompt | Out-Null
    Update-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Changes @{
        TerminalLaunchStatus = 'awaiting-task-run'
        TerminalLaunchDetail = "registered '$taskName' in .vscode/tasks.json (cwd = worktree, harness gets the brief as initial prompt); start via Terminal > Run Task"
    } | Out-Null
    Write-Output "worktree   : $wtPath (branch $branch)"
    Write-Output "task       : '$taskName' registered in .vscode/tasks.json"
    Write-Output "next       : Ctrl+Shift+P > Tasks: Run Task > '$taskName' - it starts in this window's terminal panel"
    exit 0
}
elseif ($Backend -eq 'vscode') {
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
