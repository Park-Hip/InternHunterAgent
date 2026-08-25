# mate_watch.ps1 - background event watcher for crew mode.
# Sleeps between sweeps; appends structured events to .crew/events.log when
# something changes. Zero tokens: pure script, no agent involved.
# The mate reconciles from events.log and crew_board.ps1 on its next turn.

[CmdletBinding()]
param(
    [int]$IntervalSec = 60,
    # Single sweep then exit; used by tests and manual verification.
    [switch]$Once,
    [string]$RepoRoot
)

if (-not $RepoRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $RepoRoot = Split-Path -Parent $scriptDir
}

$ErrorActionPreference = 'Stop'
Set-Location $RepoRoot

$logPath = Join-Path $RepoRoot '.crew\events.log'
$statePath = Join-Path $RepoRoot '.crew\.watch-state.json'

function Write-Event {
    param([string]$Subject, [string]$Event, [string]$Detail = '')
    $line = '{0:u} | {1} | {2} | {3}' -f (Get-Date).ToUniversalTime(), $Subject, $Event, $Detail
    # PS 5.1 has no utf8NoBOM encoding enum on Add-Content; write bytes directly.
    [System.IO.File]::AppendAllText($logPath, "$line`r`n", [System.Text.UTF8Encoding]::new($false))
    Write-Verbose $line
}

function Get-CrewBranches {
    $raw = git worktree list --porcelain
    $branches = @()
    $inCrewRecord = $false
    foreach ($line in $raw) {
        if ($line -like 'worktree *') {
            $inCrewRecord = ((Split-Path -Leaf $line.Substring('worktree '.Length)) -match '^IHA-(\d+)$')
        }
        elseif ($inCrewRecord -and $line -like 'branch *') {
            $branches += @{ Branch = ($line.Substring('branch '.Length)) -replace '^refs/heads/', '' }
        }
    }
    return $branches
}

function Get-Signature {
    param([hashtable]$Entry)
    $prJson = gh pr view $Entry.Branch --json number,state,statusCheckRollup,reviewDecision 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $prJson) { return 'no-pr' }
    $pr = $prJson | ConvertFrom-Json
    $failed = @($pr.statusCheckRollup | Where-Object { $_.conclusion -eq 'FAILURE' }).Count
    $pending = @($pr.statusCheckRollup | Where-Object { $_.status -ne 'COMPLETED' }).Count
    $checks = if ($failed -gt 0) { "fail:$failed" } elseif ($pending -gt 0) { "pending:$pending" } else { 'green' }
    return 'pr#{0}|{1}|{2}|{3}' -f $pr.number, $pr.state, $checks, $pr.reviewDecision
}

function Get-StatusSignature {
    param([string]$Issue)
    $f = Join-Path $RepoRoot ".crew\$Issue-status.md"
    if (-not (Test-Path $f)) { return '' }
    return ((Get-Content $f -Raw -ErrorAction SilentlyContinue) -replace '\s', '')
}

$state = @{ Signatures = @{} }
if (Test-Path $statePath) {
    try { $state = Get-Content $statePath -Raw | ConvertFrom-Json -AsHashtable } catch { }
}

while ($true) {
    foreach ($entry in (Get-CrewBranches)) {
        $issue = if ($entry.Branch -match '(?:^|/)(?:iha|crew)-?(\d+)') { $Matches[1] } else { $entry.Branch }
        $sig = Get-Signature $entry
        $prev = if ($state.Signatures.ContainsKey($entry.Branch)) { $state.Signatures[$entry.Branch] } else { '' }

        if ($sig -ne $prev) {
            if ($prev -eq '' -and $sig -ne 'no-pr') {
                Write-Event "crew/$issue" 'PR_OPENED' ("branch=$($entry.Branch)")
            }
            elseif ($sig -eq 'no-pr') {
                Write-Event "crew/$issue" 'PR_GONE' ("branch=$($entry.Branch)")
            }
            elseif ($sig -like '*|MERGED|*') {
                Write-Event "crew/$issue" 'PR_MERGED' ("branch=$($entry.Branch)")
            }
            elseif ($sig -like '*|green|*') {
                if     ($sig -like '*|APPROVED')   { Write-Event "crew/$issue" 'PR_LANDABLE' 'checks green + approved; auto-merge will land it' }
                elseif ($sig -like '*REVIEW_REQUIRED') { Write-Event "crew/$issue" 'PR_READY_FOR_REVIEW' 'checks green; awaiting maintainer approval' }
                else                                { Write-Event "crew/$issue" 'CHECKS_GREEN' ("state=$($sig)") }
            }
            elseif ($sig -like '*fail:*') {
                Write-Event "crew/$issue" 'CHECKS_FAILED' ("branch=$($entry.Branch) sig=$sig")
            }
            $state.Signatures[$entry.Branch] = $sig
        }

        $stSig = Get-StatusSignature $issue
        $stKey = "$($entry.Branch)#status"
        $prevSt = if ($state.Signatures.ContainsKey($stKey)) { $state.Signatures[$stKey] } else { '' }
        if ($stSig -ne $prevSt -and $stSig -ne '') {
            Write-Event "crew/$issue" 'WORKER_STATUS_CHANGED' ''
            $state.Signatures[$stKey] = $stSig
        }
    }

    $state | ConvertTo-Json -Depth 4 | ForEach-Object {
        [System.IO.File]::WriteAllText($statePath, $_, [System.Text.UTF8Encoding]::new($false))
    }

    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSec
}
