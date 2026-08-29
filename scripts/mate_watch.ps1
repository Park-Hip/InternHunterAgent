# mate_watch.ps1 - background event watcher for crew mode.
# Sleeps between sweeps; appends structured events to .crew/events.log when
# something changes, raises Windows toasts for escalation-grade events, and
# detects worker completion directly (scout report ready, idle worktree) and
# worker health through a durable heartbeat (stalled versus live-but-quiet).
# Zero tokens: pure script, no agent involved.
# The mate reconciles from events.log and crew_board.ps1 on its next turn.

[CmdletBinding()]
param(
    [int]$IntervalSec = 60,
    # Sweeps a worktree's dirty-file count may stay unchanged before WORKER_IDLE fires.
    [ValidateRange(1, 120)][int]$IdleSweeps = 5,
    # Seconds a worker's heartbeat may be stale before WORKER_STALLED fires.
    [ValidateRange(30, 86400)][int]$StalledAfterSec = 900,
    # Suppress Windows toast notifications for escalation-grade events.
    [switch]$NoToast,
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

# Events that deserve an OS notification because they need a human decision or action.
$toastEvents = @('PR_READY_FOR_REVIEW', 'PR_LANDABLE', 'CHECKS_FAILED', 'PR_MERGED', 'SCOUT_REPORT_READY', 'WORKER_STALLED')

function Write-Event {
    param([string]$Subject, [string]$Event, [string]$Detail = '')
    $line = '{0:u} | {1} | {2} | {3}' -f (Get-Date).ToUniversalTime(), $Subject, $Event, $Detail
    # PS 5.1 has no utf8NoBOM encoding enum on Add-Content; write bytes directly.
    [System.IO.File]::AppendAllText($logPath, "$line`r`n", [System.Text.UTF8Encoding]::new($false))
    Write-Verbose $line
    if ($toastEvents -contains $Event -and -not $NoToast) {
        Send-CrewToast -Title "Crew $Subject" -Message "$Event $Detail"
    }
}

function Send-CrewToast {
    param([string]$Title, [string]$Message)
    try {
        $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
        $escape = { param($s) [System.Security.SecurityElement]::Escape($s) }
        $xmlText = "<toast><visual><binding template='ToastGeneric'><text>$(& $escape $Title)</text><text>$(& $escape $Message)</text></binding></visual></toast>"
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($xmlText)
        $toast = New-Object Windows.UI.Notifications.ToastNotification($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
    }
    catch {
        Write-Verbose "toast failed: $($_.Exception.Message)"
    }
}

function Get-CrewBranches {
    $raw = git worktree list --porcelain
    $branches = @()
    $inCrewRecord = $false
    foreach ($line in $raw) {
        if ($line -like 'worktree *') {
            $path = $line.Substring('worktree '.Length)
            $inCrewRecord = ((Split-Path -Leaf $path) -match '^IHA-(\d+)$')
            if ($inCrewRecord) { $script:currentCrewPath = $path }
        }
        elseif ($inCrewRecord -and $line -like 'branch *') {
            $branches += @{
                Branch = ($line.Substring('branch '.Length)) -replace '^refs/heads/', ''
                Path   = $script:currentCrewPath
            }
        }
    }
    return $branches
}

function Get-CrewTaskManifestInfo {
    param([string]$Issue)
    $manifestPath = Join-Path $RepoRoot ".crew\$Issue-task.json"
    if (-not (Test-Path $manifestPath)) { return @{ Autonomy = $null; ScoutReportPath = $null } }
    try {
        $m = Get-Content $manifestPath -Raw | ConvertFrom-Json
        return @{ Autonomy = $m.Autonomy; ScoutReportPath = $m.ScoutReportPath }
    }
    catch {
        return @{ Autonomy = $null; ScoutReportPath = $null }
    }
}

function Get-Signature {
    param([hashtable]$Entry)
    # gh writes errors to stderr; under a Stop preference a redirected stderr
    # record would terminate the whole sweep. Survive gh failures instead.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $prJson = & gh pr view $Entry.Branch --json number,state,headRefOid,statusCheckRollup,reviewDecision 2>$null
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
    if ($LASTEXITCODE -ne 0 -or -not $prJson) { return 'no-pr' }
    $pr = $prJson | ConvertFrom-Json
    $failed = @($pr.statusCheckRollup | Where-Object { $_.conclusion -eq 'FAILURE' }).Count
    $pending = @($pr.statusCheckRollup | Where-Object { $_.status -ne 'COMPLETED' }).Count
    $checks = if ($failed -gt 0) { "fail:$failed" } elseif ($pending -gt 0) { "pending:$pending" } else { 'green' }
    $reviewRecords = @()
    $repoJson = & gh repo view --json nameWithOwner 2>$null
    if ($LASTEXITCODE -eq 0 -and $repoJson) {
        try {
            $repo = $repoJson | ConvertFrom-Json
            if ($repo.nameWithOwner) {
                $reviewJson = & gh api --paginate --slurp "repos/$($repo.nameWithOwner)/pulls/$($pr.number)/reviews?per_page=100" 2>$null
                if ($LASTEXITCODE -eq 0 -and $reviewJson) {
                    $reviewPages = $reviewJson | ConvertFrom-Json
                    foreach ($page in @($reviewPages)) { $reviewRecords += @($page) }
                }
            }
        }
        catch { $reviewRecords = @() }
    }
    $marker = if ($pr.headRefOid) { '(?im)^Reviewed head:\s*' + [regex]::Escape([string]$pr.headRefOid) + '\s*$' } else { $null }
    $skillVerdict = [bool]$marker -and @($reviewRecords | Where-Object {
        $_.commit_id -eq $pr.headRefOid -and $_.state -eq 'COMMENTED' -and $_.body -match '(?i)/code-review' -and $_.body -match '(?i)\bpass(ing|ed)?\b' -and $_.body -match $marker
    }).Count -gt 0
    $skillState = if ($skillVerdict) { 'skill:pass' } else { 'skill:missing' }
    return 'pr#{0}|{1}|{2}|{3}|{4}' -f $pr.number, $pr.state, $checks, $pr.reviewDecision, $skillState
}

function Get-StatusSignature {
    param([string]$Issue)
    $f = Join-Path $RepoRoot ".crew\$Issue-status.md"
    if (-not (Test-Path $f)) { return '' }
    return ((Get-Content $f -Raw -ErrorAction SilentlyContinue) -replace '\s', '')
}

function Get-CrewHeartbeat {
    param([string]$Issue)
    $f = Join-Path $RepoRoot ".crew\$Issue-heartbeat.json"
    if (-not (Test-Path -LiteralPath $f)) { return $null }
    try { return (Get-Content -LiteralPath $f -Raw | ConvertFrom-Json) }
    catch { return $null }
}

function Get-CrewHeartbeatAgeSeconds {
    param($Heartbeat)
    if (-not $Heartbeat -or -not $Heartbeat.updatedAtUtc) { return $null }
    try {
        $parsed = [DateTimeOffset]::Parse([string]$Heartbeat.updatedAtUtc, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal)
    }
    catch { return $null }
    return ([DateTimeOffset]::UtcNow - $parsed.ToUniversalTime()).TotalSeconds
}

$state = @{ Signatures = @{} }
if (Test-Path $statePath) {
    try {
        # -AsHashtable needs PS 6+; convert PSCustomObject manually for 5.1 compat.
        $jsonState = Get-Content $statePath -Raw | ConvertFrom-Json
        $signatures = @{}
        foreach ($prop in $jsonState.Signatures.PSObject.Properties) { $signatures[$prop.Name] = [string]$prop.Value }
        $state = @{ Signatures = $signatures }
    } catch { }
}

while ($true) {
    foreach ($entry in (Get-CrewBranches)) {
        $issue = if ($entry.Branch -match '(?:^|/)(?:iha|crew)-?(\d+)') { $Matches[1] }
                elseif ($entry.Branch -match '^crew/(\d+)') { $Matches[1] }
                else { $entry.Branch }
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
                if     ($sig -like '*|skill:missing') { Write-Event "crew/$issue" 'PR_READY_FOR_REVIEW' 'checks green; independent current-head /code-review verdict required' }
                elseif ($sig -like '*|APPROVED|skill:pass') { Write-Event "crew/$issue" 'PR_LANDABLE' 'checks green + current /code-review verdict + maintainer approval; auto-merge will land it' }
                elseif ($sig -like '*|skill:pass') { Write-Event "crew/$issue" 'PR_READY_FOR_REVIEW' 'checks green + current /code-review verdict; awaiting maintainer approval' }
                else { Write-Event "crew/$issue" 'CHECKS_GREEN' ("state=$($sig)") }
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

        # Completion detection: scout durable report appearing.
        $manifestInfo = Get-CrewTaskManifestInfo -Issue $issue
        $scoutKey = "$($entry.Branch)#scout"
        if ($manifestInfo.Autonomy -eq 'scout' -and $manifestInfo.ScoutReportPath -and (Test-Path $manifestInfo.ScoutReportPath)) {
            if ($state.Signatures[$scoutKey] -ne 'ready') {
                Write-Event "crew/$issue" 'SCOUT_REPORT_READY' ("report=$($manifestInfo.ScoutReportPath)")
                $state.Signatures[$scoutKey] = 'ready'
            }
        }

        # Health detection: a heartbeat older than StalledAfterSec means the worker
        # is stalled; a fresh heartbeat means it is alive even if quiet. A missing
        # heartbeat is not a stall - crew_start writes the first heartbeat and legacy
        # tasks may predate the contract.
        $heartbeat = Get-CrewHeartbeat -Issue $issue
        $stallKey = "$($entry.Branch)#stall"
        $prevStall = if ($state.Signatures.ContainsKey($stallKey)) { $state.Signatures[$stallKey] } else { '' }
        $stalled = $false
        if ($heartbeat -and -not ($sig -like '*|MERGED|*')) {
            $ageSec = Get-CrewHeartbeatAgeSeconds -Heartbeat $heartbeat
            if ($null -ne $ageSec -and $ageSec -ge $StalledAfterSec) {
                $scoutDone = ($manifestInfo.Autonomy -eq 'scout' -and $manifestInfo.ScoutReportPath -and (Test-Path -LiteralPath $manifestInfo.ScoutReportPath))
                if (-not $scoutDone) { $stalled = $true }
            }
        }
        if ($stalled) {
            if ($prevStall -ne 'stalled') {
                Write-Event "crew/$issue" 'WORKER_STALLED' ("heartbeat age {0:N0}s >= {1}s; phase '{2}'" -f $ageSec, $StalledAfterSec, $heartbeat.phase)
                $state.Signatures[$stallKey] = 'stalled'
            }
        }
        elseif ($prevStall -eq 'stalled') {
            $state.Signatures[$stallKey] = 'cleared'
        }

        # Completion detection: unchanged dirty-file count across IdleSweeps sweeps.
        $dirtyCount = @(git -C $entry.Path status --porcelain).Count
        $idleKey = "$($entry.Branch)#idle"
        $idleState = if ($state.Signatures.ContainsKey($idleKey)) { $state.Signatures[$idleKey] } else { "count:$dirtyCount|sweeps:0|emitted:no" }
        $parts = $idleState -split '\|'
        $prevCount = ($parts[0] -replace '^count:', '')
        $sweepN = [int]($parts[1] -replace '^sweeps:', '')
        $emitted = ($parts[2] -replace '^emitted:', '')
        if ($prevCount -ne "$dirtyCount") { $sweepN = 0; $emitted = 'no' }
        else { $sweepN++ }
        if ($sweepN -ge $IdleSweeps -and $emitted -eq 'no') {
            Write-Event "crew/$issue" 'WORKER_IDLE' ("unchanged dirty count $dirtyCount across $IdleSweeps sweeps")
            $emitted = 'yes'
        }
        $state.Signatures[$idleKey] = "count:$dirtyCount|sweeps:$sweepN|emitted:$emitted"
    }

    $state | ConvertTo-Json -Depth 4 | ForEach-Object {
        [System.IO.File]::WriteAllText($statePath, $_, [System.Text.UTF8Encoding]::new($false))
    }

    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSec
}
