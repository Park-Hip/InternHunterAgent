# crew_teardown.ps1 - safely retire one crew task using its durable manifest.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][int]$Issue,
    [switch]$ConfirmScoutReportHandoff,
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

$paths = Get-CrewTaskPaths -RepoRoot $RepoRoot -Issue $Issue
$manifest = Read-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath
if ($manifest.RepoRoot -ne $RepoRoot) {
    throw "Manifest repository '$($manifest.RepoRoot)' does not match '$RepoRoot'. Teardown is refused."
}
if ($manifest.State -eq 'torn_down') {
    throw "Crew task #$Issue is already torn down."
}
if (-not (Test-Path -LiteralPath $manifest.WorktreePath)) {
    throw "Worktree missing at '$($manifest.WorktreePath)'. Teardown is refused for manual recovery."
}

Assert-CrewTeardownAllowed -Manifest $manifest -ConfirmScoutReportHandoff:$ConfirmScoutReportHandoff

if ($WhatIfMode) {
    Write-Output 'dry-run teardown (no changes made):'
    Write-Output ("  worktree : git worktree remove `"{0}`"" -f $manifest.WorktreePath)
    if ($manifest.Autonomy -eq 'scout') {
        Write-Output ("  report   : confirmed durable at {0}" -f $manifest.ScoutReportPath)
    }
    if ($manifest.TerminalBackend -eq 'vscode-task') {
        Write-Output "  vscode-task : remove Run Task entries with cwd '$($manifest.WorktreePath)' from .vscode\tasks.json"
    }
    if ($manifest.TerminalBackend -eq 'vscode-task-auto') {
        Write-Output "  vscode-task-auto : remove Run Task entries with cwd '$($manifest.WorktreePath)' from .vscode\tasks.json"
        Write-Output "  vscode-task-auto : remove request and result records for launch request '$($manifest.LaunchRequestId)'"
    }
    Write-Output ("  manifest : mark .crew\{0}-task.json as torn_down" -f $Issue)
    exit 0
}

git worktree remove $manifest.WorktreePath
if ($LASTEXITCODE -ne 0) { throw "git worktree remove failed for '$($manifest.WorktreePath)'." }

$changes = @{
    State = 'torn_down'
    TornDownAtUtc = '{0:u}' -f (Get-Date).ToUniversalTime()
}
if ($manifest.Autonomy -eq 'scout' -and -not $manifest.ScoutReportHandedOff) {
    $changes.ScoutReportHandedOff = $true
}
Update-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Changes $changes | Out-Null

if ($manifest.TerminalBackend -eq 'vscode-task' -or $manifest.TerminalBackend -eq 'vscode-task-auto') {
    . (Join-Path $PSScriptRoot 'crew_vscode_backend.ps1')
    $taskEntry = Remove-CrewVsCodeTaskEntry -RepoRoot $RepoRoot -WorktreePath $manifest.WorktreePath
    $backendLabel = $manifest.TerminalBackend
    if ($taskEntry.Removed -gt 0) {
        Write-Output ("{0} : removed {1} matching Run Task entry from {2}" -f $backendLabel, $taskEntry.Removed, $taskEntry.TasksPath)
    }
    else {
        Write-Output ("{0} : no matching Run Task entry found in {1}" -f $backendLabel, $taskEntry.TasksPath)
    }
    if ($manifest.TerminalBackend -eq 'vscode-task-auto' -and $manifest.LaunchRequestId) {
        $records = Remove-CrewVsCodeAutoRecords -RepoRoot $RepoRoot -RequestId $manifest.LaunchRequestId
        Write-Output ("vscode-task-auto : removed {0} launch-queue record(s) for request {1}" -f $records.Removed, $manifest.LaunchRequestId)
    }
}

Write-Output "teardown    : crew task #$Issue worktree removed"
Write-Output ("manifest    : {0}" -f $paths.PrimaryManifestPath)
