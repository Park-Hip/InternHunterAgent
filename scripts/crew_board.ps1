# crew_board.ps1 - current-state read for crew mode.
# One command, one glance: every crew worktree with its branch, dirty-file count,
# last worker status line, heartbeat age, and PR verdict (checks + review decision).
# Used by the mate on every turn and by the maintainer directly.

[CmdletBinding()]
param(
    [string]$RepoRoot
)

if (-not $RepoRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $RepoRoot = Split-Path -Parent $scriptDir
}

$ErrorActionPreference = 'Stop'
Set-Location $RepoRoot

$raw = git worktree list --porcelain
$crews = @()
$inCrewRecord = $false
foreach ($line in $raw) {
    if ($line -like 'worktree *') {
        $path = $line.Substring('worktree '.Length)
        $inCrewRecord = ((Split-Path -Leaf $path) -match '^IHA-(\d+)$')
        if ($inCrewRecord) { $script:currentPath = $path; $script:currentIssue = $Matches[1] }
    }
    elseif ($inCrewRecord -and $line -like 'branch *') {
        $branchName = ($line.Substring('branch '.Length)) -replace '^refs/heads/', ''
        $crews += @{
            Issue  = $script:currentIssue
            Path   = $script:currentPath
            Branch = $branchName
        }
    }
}

if ($crews.Count -eq 0) {
    Write-Output 'no active crew'
    exit 0
}

foreach ($c in $crews) {
    $dirty = @(git -C $c.Path status --porcelain).Count

    $statusFile = Join-Path $RepoRoot ".crew\$($c.Issue)-status.md"
    $status = '(no status recorded)'
    if (Test-Path $statusFile) {
        $last = Get-Content $statusFile | Where-Object { $_.Trim() } | Select-Object -Last 1
        if ($last) { $status = $last.Trim() }
    }

    $heartbeatLine = 'none'
    $heartbeatFile = Join-Path $RepoRoot ".crew\$($c.Issue)-heartbeat.json"
    if (Test-Path -LiteralPath $heartbeatFile) {
        try {
            $hb = Get-Content -LiteralPath $heartbeatFile -Raw | ConvertFrom-Json
            $hbText = [string]$hb.phase
            try {
                $hbTime = [DateTimeOffset]::Parse([string]$hb.updatedAtUtc, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal)
                $hbAge = [DateTimeOffset]::UtcNow - $hbTime.ToUniversalTime()
                $hbText = "{0} · {1}m ago" -f $hb.phase, [int]$hbAge.TotalMinutes
            }
            catch { }
            $heartbeatLine = $hbText
        }
        catch { $heartbeatLine = 'unreadable' }
    }

    $prLine = '(no PR yet)'
    $prJson = gh pr view $c.Branch --json number,state,url,statusCheckRollup,reviewDecision 2>$null
    if ($LASTEXITCODE -eq 0 -and $prJson) {
        $pr = $prJson | ConvertFrom-Json
        $failed  = @($pr.statusCheckRollup | Where-Object { $_.conclusion -eq 'FAILURE' }).Count
        $pending = @($pr.statusCheckRollup | Where-Object { $_.status -ne 'COMPLETED' }).Count
        $checks = if ($failed -gt 0) { "CHECKS FAILING ($failed)" }
                  elseif ($pending -gt 0) { "checks pending ($pending)" }
                  else { 'checks GREEN' }
        # No-mistakes gate status.
        $issueNum = if ($c.Branch -match '(?:^|/)(?:iha|crew)-?(\d+)') { $Matches[1] }
                   elseif ($c.Branch -match '^crew/(\d+)') { $Matches[1] } else { $null }
        $nmPath = if ($issueNum) { Join-Path $RepoRoot ".crew\$issueNum-no-mistakes.json" } else { $null }
        $nmStatus = 'nm:NONE'
        if ($nmPath -and (Test-Path -LiteralPath $nmPath)) {
            try {
                $nm = Get-Content -LiteralPath $nmPath -Raw | ConvertFrom-Json
                $nmStatus = if ($nm.head_sha -eq $pr.headRefOid) { 'nm:PASSED' } else { 'nm:STALE' }
            } catch { $nmStatus = 'nm:ERROR' }
        }
        $prLine = '#{0} [{1}] {2}; {3}; {4}' -f $pr.number, $pr.state, $checks, $nmStatus, $pr.url
    }

    Write-Output ('---')
    Write-Output ('issue #{0}  branch {1}  ({2} dirty files)' -f $c.Issue, $c.Branch, $dirty)
    Write-Output ('worker : {0}' -f $status)
    Write-Output ('beat   : {0}' -f $heartbeatLine)
    Write-Output ('pr     : {0}' -f $prLine)
}

Write-Output ('===')
Write-Output 'events tail:'
Get-Content (Join-Path $RepoRoot '.crew\events.log') -Tail 5 -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output ("  " + $_) }
