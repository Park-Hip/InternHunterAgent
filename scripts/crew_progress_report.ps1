# crew_progress_report.ps1 - durable, captain-facing crew progress reports.
# Reads only crew state already owned by manifests, statuses, events, Git worktrees,
# GitHub PR state, and optional ignored candidate records.

[CmdletBinding()]
param(
    [ValidateSet('html', 'markdown', 'data')][string]$Format = 'html',
    [string]$RepoRoot,
    [string]$CandidatePath,
    [string]$OutputPath,
    [switch]$SkipGitHub,
    # Test seam: defaults to the GitHub CLI used by normal reports.
    [string]$GitHubCommand = 'gh'
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$crewRoot = Join-Path $RepoRoot '.crew'
if (-not $CandidatePath) { $CandidatePath = Join-Path $crewRoot 'candidates.json' }

function Get-LastNonEmptyLine {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return (Get-Content -LiteralPath $Path | Where-Object { $_.Trim() } | Select-Object -Last 1).Trim()
}

function Get-TaskPrState {
    param($Task)
    $unknown = [pscustomobject]@{
        Number = $null; Url = $null; State = 'No pull request'; Checks = 'Unknown';
        Review = 'Unknown'; Summary = 'No pull request'; Failure = $false; AwaitingReview = $false; Landable = $false
    }
    if ($SkipGitHub) { return $unknown }

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $raw = & $GitHubCommand pr view $Task.Branch --json number,state,url,statusCheckRollup,reviewDecision 2>$null }
    finally { $ErrorActionPreference = $oldPreference }
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $unknown }

    try { $pr = $raw | ConvertFrom-Json } catch { return $unknown }
    $checks = @($pr.statusCheckRollup)
    $failed = @($checks | Where-Object { $_.conclusion -eq 'FAILURE' }).Count
    $pending = @($checks | Where-Object { $_.status -and $_.status -ne 'COMPLETED' }).Count
    $checkText = if ($failed -gt 0) { "Checks failing ($failed)" }
                 elseif ($pending -gt 0) { "Checks pending ($pending)" }
                 else { 'Checks green' }
    $reviewText = switch ($pr.reviewDecision) {
        'APPROVED' { 'Approved' }
        'REVIEW_REQUIRED' { 'Awaiting maintainer approval' }
        $null { 'No review decision' }
        '' { 'No review decision' }
        default { [string]$pr.reviewDecision }
    }
    $summary = "#$($pr.number) [$($pr.state)]; $checkText; review: $reviewText"
    return [pscustomobject]@{
        Number = $pr.number; Url = $pr.url; State = $pr.state; Checks = $checkText; Review = $reviewText; Summary = $summary
        Failure = ($failed -gt 0); AwaitingReview = ($failed -eq 0 -and $pending -eq 0 -and $pr.reviewDecision -eq 'REVIEW_REQUIRED')
        Landable = ($failed -eq 0 -and $pending -eq 0 -and $pr.reviewDecision -eq 'APPROVED')
    }
}

function Test-SharedSurface {
    param([string]$Path)
    $normal = $Path -replace '\\', '/'
    return $normal -eq 'config/settings.yaml' -or $normal -match '^src/(?:.*/)?models\.py$'
}

function Get-ActiveTasks {
    $warnings = [System.Collections.Generic.List[string]]::new()
    $tasks = [System.Collections.Generic.List[object]]::new()
    if (-not (Test-Path -LiteralPath $crewRoot)) { return [pscustomobject]@{ Tasks = $tasks; Warnings = $warnings } }

    foreach ($file in @(Get-ChildItem -LiteralPath $crewRoot -Filter '*-task.json' -File -ErrorAction SilentlyContinue | Sort-Object Name)) {
        try { $manifest = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json }
        catch { $warnings.Add("Ignored malformed manifest: $($file.Name)"); continue }
        if ($manifest.State -eq 'torn_down') { continue }
        if ($null -eq $manifest.Issue -or -not $manifest.Branch) {
            $warnings.Add("Ignored incomplete manifest: $($file.Name)"); continue
        }

        $statusPath = if ($manifest.PrimaryStatusPath) { $manifest.PrimaryStatusPath } else { Join-Path $crewRoot "$($manifest.Issue)-status.md" }
        $worktreeExists = [bool]($manifest.WorktreePath -and (Test-Path -LiteralPath $manifest.WorktreePath))
        $task = [pscustomobject]@{
            Issue = [int]$manifest.Issue; Title = [string]$manifest.Title; Autonomy = [string]$manifest.Autonomy
            Branch = [string]$manifest.Branch; DispatchedAtUtc = [string]$manifest.DispatchedAtUtc
            WorktreePath = [string]$manifest.WorktreePath; WorktreeExists = $worktreeExists
            Status = Get-LastNonEmptyLine -Path $statusPath; ScoutReportPath = [string]$manifest.ScoutReportPath
            FilesInScope = @(); Pr = $null
        }
        if ($manifest.PrimaryBriefPath -and (Test-Path -LiteralPath $manifest.PrimaryBriefPath)) {
            $briefText = Get-Content -LiteralPath $manifest.PrimaryBriefPath -Raw
            $scopeMatch = [regex]::Match($briefText, '(?ms)^## Files in scope\s*$(.*?)(?=^## |\z)')
            if ($scopeMatch.Success) { $task.FilesInScope = @($scopeMatch.Groups[1].Value -split "`r?`n" | ForEach-Object { $_.Trim() -replace '^[-*]\s+', '' } | Where-Object { $_ }) }
        }
        $task.Pr = Get-TaskPrState -Task $task
        $tasks.Add($task)
    }
    return [pscustomobject]@{ Tasks = $tasks; Warnings = $warnings }
}

function Get-CandidateRecords {
    param($ActiveTasks)
    $warnings = [System.Collections.Generic.List[string]]::new()
    $candidates = [System.Collections.Generic.List[object]]::new()
    if (-not (Test-Path -LiteralPath $CandidatePath)) {
        return [pscustomobject]@{ Candidates = $candidates; Warnings = $warnings; SourceState = 'No candidate record exists.' }
    }
    try { $raw = Get-Content -LiteralPath $CandidatePath -Raw | ConvertFrom-Json }
    catch { return [pscustomobject]@{ Candidates = $candidates; Warnings = @("Candidate record is malformed: $CandidatePath"); SourceState = 'Candidate record is malformed.' } }
    if ($null -eq $raw.candidates) {
        return [pscustomobject]@{ Candidates = $candidates; Warnings = @("Candidate record has no candidates array: $CandidatePath"); SourceState = 'Candidate record has no candidates array.' }
    }

    foreach ($item in @($raw.candidates)) {
        $evidence = $item.evidence
        $valid = $null -ne $item.issue -and $item.type -in @('ship', 'scout') -and $item.goal -and $null -ne $item.filesInScope -and
                 $item.planStatus -and $item.compatibility -and $null -ne $evidence -and $evidence.source -and $evidence.heading -and $evidence.label -and $evidence.excerpt
        if (-not $valid) { $warnings.Add('Ignored candidate with a missing required field.'); continue }
        $files = @($item.filesInScope | ForEach-Object { [string]$_ })
        $compatibility = ''
        $reason = ''
        if ([string]$item.planStatus -ne 'approved') {
            $compatibility = 'waiting'; $reason = 'Plan approval is required.'
        }
        elseif ($item.type -eq 'ship') {
            $conflicts = @()
            foreach ($file in $files) {
                if (Test-SharedSurface $file) {
                    foreach ($task in $ActiveTasks | Where-Object { $_.Autonomy -eq 'ship' }) {
                        if (@($task.FilesInScope | Where-Object { Test-SharedSurface $_ }).Count -gt 0) { $conflicts += "#$($task.Issue)" }
                    }
                }
            }
            if ($conflicts.Count -gt 0) { $compatibility = 'waiting'; $reason = "Shared-surface lock with $(($conflicts | Select-Object -Unique) -join ', ')." }
        }
        if (-not $compatibility -and [string]$item.compatibility -ne 'clear') {
            $compatibility = 'waiting'; $reason = "Candidate record says: $($item.compatibility)"
        }
        if (-not $compatibility) { $compatibility = 'dispatchable'; $reason = 'Plan approved; no active shared-surface lock found.' }
        $candidates.Add([pscustomobject]@{
            Issue = [int]$item.issue; Type = [string]$item.type; Goal = [string]$item.goal; FilesInScope = $files
            PlanStatus = [string]$item.planStatus; RecordCompatibility = [string]$item.compatibility
            Compatibility = $compatibility; CompatibilityReason = $reason
            Evidence = [pscustomobject]@{ Source = [string]$evidence.source; Heading = [string]$evidence.heading; Label = [string]$evidence.label; Excerpt = [string]$evidence.excerpt }
        })
    }
    return [pscustomobject]@{ Candidates = $candidates; Warnings = $warnings; SourceState = "$($candidates.Count) candidate record(s) read." }
}

function Get-RecentEvents {
    $eventPath = Join-Path $crewRoot 'events.log'
    if (-not (Test-Path -LiteralPath $eventPath)) { return @() }
    return @(Get-Content -LiteralPath $eventPath | Where-Object { $_.Trim() } | Select-Object -Last 10 | ForEach-Object {
        $rawLine = [string]$_
        $parts = $rawLine -split ' \| ', 4
        [pscustomobject]@{ Timestamp = $parts[0]; Subject = if ($parts.Count -gt 1) { $parts[1] } else { '' }; Event = if ($parts.Count -gt 2) { $parts[2] } else { '' }; Detail = if ($parts.Count -gt 3) { $parts[3] } else { '' }; Raw = $rawLine }
    })
}

$activeResult = Get-ActiveTasks
$tasks = @($activeResult.Tasks | Sort-Object Issue)
$candidateResult = Get-CandidateRecords -ActiveTasks $tasks
$actions = [System.Collections.Generic.List[string]]::new()
$risks = [System.Collections.Generic.List[string]]::new()
foreach ($task in $tasks) {
    if (-not $task.WorktreeExists) { $risks.Add("#$($task.Issue): manifest names a missing worktree: $($task.WorktreePath)") }
    if ($task.Pr.Failure) { $actions.Add("#$($task.Issue): resolve failing checks on PR #$($task.Pr.Number)."); $risks.Add("#$($task.Issue): $($task.Pr.Checks).") }
    elseif ($task.Pr.AwaitingReview) { $actions.Add("#$($task.Issue): review PR #$($task.Pr.Number) for approval.") }
    if ($task.Autonomy -eq 'scout' -and $task.ScoutReportPath -and (Test-Path -LiteralPath $task.ScoutReportPath)) { $actions.Add("#$($task.Issue): read the durable scout report before deciding follow-up.") }
    if ($task.Status -and $task.Status -match '^(blocked|risk)\b') { $risks.Add("#$($task.Issue): worker status: $($task.Status)") }
}
$landingOrder = @($tasks | Where-Object { $_.Autonomy -eq 'ship' } | Sort-Object @{ Expression = { if ($_.DispatchedAtUtc) { $_.DispatchedAtUtc } else { '9999' } } }, Issue | ForEach-Object {
    [pscustomobject]@{ Issue = $_.Issue; Title = $_.Title; Pr = $_.Pr.Summary; Basis = 'Oldest dispatched active ship first.' }
})
$report = [pscustomobject]@{
    SchemaVersion = 1
    GeneratedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    Repository = $RepoRoot
    MaintainerActions = @($actions)
    ActiveTasks = $tasks
    Risks = @($risks)
    LandingOrder = $landingOrder
    RecentMaterialChanges = @(Get-RecentEvents)
    NextCompatibleTasks = @($candidateResult.Candidates | Sort-Object Issue)
    EmptyStates = [pscustomobject]@{
        ActiveTasks = if ($tasks.Count) { $null } else { 'No active crew tasks.' }
        Actions = if ($actions.Count) { $null } else { 'No maintainer action is currently indicated by durable state.' }
        Risks = if ($risks.Count) { $null } else { 'No risks are currently indicated by durable state.' }
        Candidates = if ($candidateResult.Candidates.Count) { $null } else { $candidateResult.SourceState }
    }
    DataWarnings = @($activeResult.Warnings) + @($candidateResult.Warnings)
}

function Encode-Html { param([object]$Value) return [System.Net.WebUtility]::HtmlEncode([string]$Value) }
function Html-List { param([object[]]$Values, [string]$Empty)
    if (-not $Values -or $Values.Count -eq 0) { return "<p class=`"empty`">$(Encode-Html $Empty)</p>" }
    return '<ul>' + (($Values | ForEach-Object { '<li>' + (Encode-Html $_) + '</li>' }) -join '') + '</ul>'
}
function Html-Section { param([string]$Title, [string]$Content, [string]$Class = '') return "<section class=`"$Class`"><h2>$(Encode-Html $Title)</h2>$Content</section>" }
function To-Markdown {
    param($Data)
    $lines = @("# Crew progress report", "Generated: $($Data.GeneratedAtUtc)", '', '## Maintainer actions')
    $lines += if ($Data.MaintainerActions.Count) { $Data.MaintainerActions | ForEach-Object { "- $_" } } else { "_($($Data.EmptyStates.Actions))_" }
    $lines += @('', '## Active tasks')
    $lines += if ($Data.ActiveTasks.Count) { $Data.ActiveTasks | ForEach-Object { "- **#$($_.Issue)** $($_.Title) ($($_.Autonomy)): $($_.Pr.Summary); status: $([string]$_.Status)" } } else { "_($($Data.EmptyStates.ActiveTasks))_" }
    $lines += @('', '## Risks')
    $lines += if ($Data.Risks.Count) { $Data.Risks | ForEach-Object { "- $_" } } else { "_($($Data.EmptyStates.Risks))_" }
    $lines += @('', '## Landing order')
    $lines += if ($Data.LandingOrder.Count) { $Data.LandingOrder | ForEach-Object { "1. #$($_.Issue) - $($_.Pr)" } } else { '_No active ship tasks._' }
    $lines += @('', '## Recent material changes')
    $lines += if ($Data.RecentMaterialChanges.Count) { $Data.RecentMaterialChanges | ForEach-Object { "- $($_.Raw)" } } else { '_No crew events recorded._' }
    $lines += @('', '## Next-compatible tasks')
    $lines += if ($Data.NextCompatibleTasks.Count) { $Data.NextCompatibleTasks | ForEach-Object { "- **#$($_.Issue)** ($($_.Type)): **$($_.Compatibility)** - $($_.CompatibilityReason) Evidence: `$($($_.Evidence.Source))` - $($_.Evidence.Heading) ($($_.Evidence.Label)): $($_.Evidence.Excerpt)" } } else { "_($($Data.EmptyStates.Candidates))_" }
    if ($Data.DataWarnings.Count) { $lines += @('', '## Data warnings'); $lines += $Data.DataWarnings | ForEach-Object { "- $_" } }
    return $lines -join "`n"
}
function To-Html {
    param($Data)
    $body = "<header><h1>Crew progress report</h1><p>Generated $(Encode-Html $Data.GeneratedAtUtc). Durable crew state reconciled at render time.</p></header>"
    $body += Html-Section 'Maintainer actions' (Html-List $Data.MaintainerActions $Data.EmptyStates.Actions)
    if ($Data.ActiveTasks.Count) {
        $rows = $Data.ActiveTasks | ForEach-Object { "<tr><td>#$($_.Issue)</td><td>$(Encode-Html $_.Title)</td><td>$(Encode-Html $_.Autonomy)</td><td>$(Encode-Html $_.Status)</td><td>$(Encode-Html $_.Pr.Summary)</td></tr>" }
        $taskBody = '<table><thead><tr><th>Issue</th><th>Task</th><th>Type</th><th>Worker status</th><th>PR state</th></tr></thead><tbody>' + ($rows -join '') + '</tbody></table>'
    } else { $taskBody = "<p class=`"empty`">$(Encode-Html $Data.EmptyStates.ActiveTasks)</p>" }
    $body += Html-Section 'Active tasks' $taskBody
    $body += Html-Section 'Risks' (Html-List $Data.Risks $Data.EmptyStates.Risks)
    $body += Html-Section 'Landing order' (Html-List @($Data.LandingOrder | ForEach-Object { "#$($_.Issue): $($_.Pr) ($($_.Basis))" }) 'No active ship tasks.')
    $body += Html-Section 'Recent material changes' (Html-List @($Data.RecentMaterialChanges | ForEach-Object { $_.Raw }) 'No crew events recorded.')
    if ($Data.NextCompatibleTasks.Count) {
        $rows = $Data.NextCompatibleTasks | ForEach-Object { "<tr><td>#$($_.Issue)</td><td>$(Encode-Html $_.Type)</td><td>$(Encode-Html $_.Goal)</td><td><span class=`"badge $($_.Compatibility)`">$(Encode-Html $_.Compatibility)</span><br>$(Encode-Html $_.CompatibilityReason)</td><td><code>$(Encode-Html $_.Evidence.Source)</code><br>$(Encode-Html $_.Evidence.Heading) - $(Encode-Html $_.Evidence.Label)<br>$(Encode-Html $_.Evidence.Excerpt)</td></tr>" }
        $candidateBody = '<table><thead><tr><th>Issue</th><th>Type</th><th>Goal</th><th>Compatibility</th><th>Evidence / provenance</th></tr></thead><tbody>' + ($rows -join '') + '</tbody></table>'
    } else { $candidateBody = "<p class=`"empty`">$(Encode-Html $Data.EmptyStates.Candidates)</p>" }
    $body += Html-Section 'Next-compatible tasks' $candidateBody
    if ($Data.DataWarnings.Count) { $body += Html-Section 'Data warnings' (Html-List $Data.DataWarnings '') 'warning' }
    $templatePath = Join-Path $PSScriptRoot 'crew_progress_report.template.html'
    if (-not (Test-Path -LiteralPath $templatePath)) { throw "Report template not found: $templatePath" }
    return (Get-Content -LiteralPath $templatePath -Raw).Replace('{{REPORT_BODY}}', $body)
}

$result = switch ($Format) { 'data' { $report | ConvertTo-Json -Depth 6 } 'markdown' { To-Markdown $report } default { To-Html $report } }
if ($OutputPath) { [System.IO.File]::WriteAllText($OutputPath, $result, [System.Text.UTF8Encoding]::new($false)) }
Write-Output $result
