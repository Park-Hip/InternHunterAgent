# test_crew_lifecycle.ps1 - deterministic probes for the native Windows crew lifecycle.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'crew_lifecycle.ps1')
. (Join-Path $PSScriptRoot 'crew_terminal_backend.ps1')
. (Join-Path $PSScriptRoot 'crew_vscode_backend.ps1')
$initialLocation = (Get-Location).Path

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Invoke-TestGit {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & git @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed." }
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("crew-lifecycle-" + [guid]::NewGuid())
try {
    $repoRoot = Join-Path $temporaryRoot 'InternHunterAgent'
    New-Item -ItemType Directory -Path $repoRoot -Force | Out-Null
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'init', '-b', 'main')
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'config', 'user.email', 'crew-probe@example.test')
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'config', 'user.name', 'Crew Lifecycle Probe')
    Write-CrewUtf8File -Path (Join-Path $repoRoot 'README.md') -Content '# Lifecycle probe'
    Write-CrewUtf8File -Path (Join-Path $repoRoot '.gitignore') -Content ".crew/[0-9]*-*.md`n.crew/[0-9]*-task.json`n"
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'add', 'README.md', '.gitignore')
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'commit', '-m', 'test: initialize crew lifecycle probe')

    New-Item -ItemType Directory -Path (Join-Path $repoRoot '.crew') -Force | Out-Null
    $paths = Get-CrewTaskPaths -RepoRoot $repoRoot -Issue 999
    Assert-Equal $paths.WorktreeRoot (Join-Path $temporaryRoot 'InternHunterAgent-worktrees') 'Worktree root calculation failed.'
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'worktree', 'add', $paths.WorktreePath, '-b', 'crew/999-lifecycle-probe', 'main')

    Write-CrewUtf8File -Path $paths.PrimaryBriefPath -Content '# Brief: lifecycle probe'
    Write-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Issue 999 -IssueUrl 'https://example.test/issues/999' -Title 'Lifecycle probe' -Autonomy scout -Branch 'crew/999-lifecycle-probe' -RepoRoot $repoRoot -WorktreePath $paths.WorktreePath -PrimaryBriefPath $paths.PrimaryBriefPath -PrimaryStatusPath $paths.PrimaryStatusPath -TaskBriefPath $paths.TaskBriefPath -ScoutReportPath $paths.ScoutReportPath -TerminalBackend wt | Out-Null
    Copy-CrewTaskContractFiles -PrimaryBriefPath $paths.PrimaryBriefPath -TaskBriefPath $paths.TaskBriefPath -PrimaryManifestPath $paths.PrimaryManifestPath -TaskManifestPath $paths.TaskManifestPath
    if (-not (Test-Path -LiteralPath $paths.TaskBriefPath)) { throw 'Task-local brief was not created.' }
    if (-not (Test-Path -LiteralPath $paths.TaskManifestPath)) { throw 'Task-local manifest was not created.' }

    try {
        & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 999 -RepoRoot $repoRoot
        throw 'Scout teardown was not refused before report handoff.'
    }
    catch {
        if ($_.Exception.Message -eq 'Scout teardown was not refused before report handoff.') { throw }
    }
    if (-not (Test-Path -LiteralPath $paths.WorktreePath)) { throw 'Refused scout teardown removed the worktree.' }

    Write-CrewUtf8File -Path $paths.ScoutReportPath -Content '# Durable scout report'
    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 999 -RepoRoot $repoRoot -ConfirmScoutReportHandoff -WhatIfMode | Out-Null
    if (-not (Test-Path -LiteralPath $paths.WorktreePath)) { throw 'Dry-run scout teardown removed the worktree.' }
    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 999 -RepoRoot $repoRoot -ConfirmScoutReportHandoff | Out-Null
    if (Test-Path -LiteralPath $paths.WorktreePath) { throw 'Confirmed scout teardown did not remove the worktree.' }
    $tornDownManifest = Read-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath
    Assert-Equal $tornDownManifest.State 'torn_down' 'Teardown did not update the manifest state.'
    Assert-Equal $tornDownManifest.ScoutReportHandedOff $true 'Teardown did not record scout report handoff.'

    # vscode-task teardown round-trip: a registered Run Task entry must be
    # removed by teardown while unrelated entries in the same file survive.
    $vscodePaths = Get-CrewTaskPaths -RepoRoot $repoRoot -Issue 998
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'worktree', 'add', $vscodePaths.WorktreePath, '-b', 'crew/998-vscode-task-probe', 'main')
    Write-CrewUtf8File -Path $vscodePaths.PrimaryBriefPath -Content '# Brief: vscode-task probe'
    Write-CrewTaskManifest -ManifestPath $vscodePaths.PrimaryManifestPath -Issue 998 -IssueUrl 'https://example.test/issues/998' -Title 'vscode-task probe' -Autonomy ship -Branch 'crew/998-vscode-task-probe' -RepoRoot $repoRoot -WorktreePath $vscodePaths.WorktreePath -PrimaryBriefPath $vscodePaths.PrimaryBriefPath -PrimaryStatusPath $vscodePaths.PrimaryStatusPath -TaskBriefPath $vscodePaths.TaskBriefPath -ScoutReportPath $vscodePaths.ScoutReportPath -TerminalBackend vscode-task | Out-Null

    $tasksPath = Join-Path $repoRoot '.vscode\tasks.json'
    $unrelatedLabel = 'Build: unrelated task'
    Add-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath 'D:\elsewhere\unrelated' -TaskName $unrelatedLabel -HarnessPath 'pi.exe' -HarnessArgs '' -WorkerPrompt 'unrelated' | Out-Null
    Add-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath $vscodePaths.WorktreePath -TaskName 'Crew: IHA-998 worker' -HarnessPath 'pi.exe' -HarnessArgs '' -WorkerPrompt 'probe' | Out-Null
    $before = Get-Content -LiteralPath $tasksPath -Raw | ConvertFrom-Json
    Assert-Equal @($before.tasks).Count 2 'Both task entries were not registered.'

    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 998 -RepoRoot $repoRoot | ForEach-Object {
        if ($_ -like 'vscode-task : removed*') { $sawRemovalReport = $true }
        $_
    } | Out-Null
    if (-not $sawRemovalReport) { throw 'Teardown did not report the vscode-task entry removal.' }
    if (Test-Path -LiteralPath $vscodePaths.WorktreePath) { throw 'vscode-task teardown did not remove the worktree.' }
    $afterJson = Get-Content -LiteralPath $tasksPath -Raw
    $after = $afterJson | ConvertFrom-Json
    Assert-Equal @($after.tasks).Count 1 'Unrelated task entry did not survive teardown.'
    Assert-Equal @($after.tasks)[0].label $unrelatedLabel 'The surviving entry is not the unrelated task.'
    $leadingBytes = [System.IO.File]::ReadAllBytes($tasksPath)[0..2]
    if ($leadingBytes[0] -eq 0xEF -and $leadingBytes[1] -eq 0xBB -and $leadingBytes[2] -eq 0xBF) { throw '.vscode/tasks.json was rewritten with a BOM.' }

    # A second teardown of an already-torn-down task is refused before any
    # removal runs; exercise Remove directly to confirm a no-match is safe.
    try {
        & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 998 -RepoRoot $repoRoot | Out-Null
        throw 'Second teardown of issue 998 was not refused.'
    }
    catch {
        if ($_.Exception.Message -eq 'Second teardown of issue 998 was not refused.') { throw }
    }
    $noMatch = Remove-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath $vscodePaths.WorktreePath
    Assert-Equal $noMatch.Removed 0 'Repeat removal should report zero entries removed.'

    $plan = New-CrewWindowsTerminalLaunchPlan -WorktreePath $paths.WorktreePath -SessionCommand 'Write-Host lifecycle-probe'
    Assert-Equal $plan.Backend 'windows-terminal' 'Terminal backend selection failed.'
    Assert-Equal $plan.FilePath 'wt.exe' 'Windows Terminal executable selection failed.'
    if ($plan.ArgumentList -notcontains '-EncodedCommand') { throw 'Windows Terminal launch plan does not encode the session command.' }
    Write-Output 'crew lifecycle probes passed'
}
finally {
    Set-Location -LiteralPath $initialLocation
    if (Test-Path -LiteralPath $repoRoot) {
        $probeWorktreeRoot = Join-Path $temporaryRoot 'InternHunterAgent-worktrees'
        Get-ChildItem -LiteralPath $probeWorktreeRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            & git -C $repoRoot worktree remove --force $_.FullName 2>$null
        }
        & git -C $repoRoot worktree prune 2>$null
    }
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
