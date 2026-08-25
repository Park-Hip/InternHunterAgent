# test_crew_lifecycle.ps1 - deterministic probes for the native Windows crew lifecycle.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'crew_lifecycle.ps1')
. (Join-Path $PSScriptRoot 'crew_terminal_backend.ps1')
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
    Write-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Issue 999 -IssueUrl 'https://example.test/issues/999' -Title 'Lifecycle probe' -Autonomy scout -Branch 'crew/999-lifecycle-probe' -RepoRoot $repoRoot -WorktreePath $paths.WorktreePath -PrimaryBriefPath $paths.PrimaryBriefPath -PrimaryStatusPath $paths.PrimaryStatusPath -TaskBriefPath $paths.TaskBriefPath -ScoutReportPath $paths.ScoutReportPath | Out-Null
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
