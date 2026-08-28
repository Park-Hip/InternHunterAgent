# test_crew_progress_report.ps1 - deterministic probes for crew progress reports.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$reportScript = Join-Path $PSScriptRoot 'crew_progress_report.ps1'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Write-Utf8 {
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}
function Write-TaskFixture {
    param([string]$Root, [int]$Issue, [string]$Autonomy, [string]$Branch, [string[]]$Scope, [string]$Status = '', [switch]$ScoutReport)
    $crew = Join-Path $Root '.crew'
    $worktree = Join-Path $Root "worktrees\IHA-$Issue"
    New-Item -ItemType Directory -Path $worktree -Force | Out-Null
    $brief = Join-Path $crew "$Issue-brief.md"
    Write-Utf8 $brief ("# Brief`n`n## Files in scope`n" + (($Scope | ForEach-Object { "- $_" }) -join "`n") + "`n`n## Out of scope`n- none`n")
    $statusPath = Join-Path $crew "$Issue-status.md"
    if ($Status) { Write-Utf8 $statusPath $Status }
    $reportPath = if ($Autonomy -eq 'scout') { Join-Path $Root "research\crew\$Issue-report.md" } else { $null }
    if ($ScoutReport) { Write-Utf8 $reportPath '# Scout handoff' }
    $manifest = [ordered]@{
        SchemaVersion = 1; Issue = $Issue; Title = "Fixture $Issue"; Autonomy = $Autonomy; Branch = $Branch
        WorktreePath = $worktree; PrimaryBriefPath = $brief; PrimaryStatusPath = $statusPath; ScoutReportPath = $reportPath
        State = 'dispatched'; DispatchedAtUtc = "2026-08-28 07:00:$Issue Z"
    }
    Write-Utf8 (Join-Path $crew "$Issue-task.json") ($manifest | ConvertTo-Json)
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("crew-progress-report-" + [guid]::NewGuid())
$oldPath = $env:PATH
try {
    New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
    Write-TaskFixture -Root $temporaryRoot -Issue 999 -Autonomy ship -Branch 'crew/999-green' -Scope @('config/settings.yaml') -Status 'WORKING: tests complete'
    Write-TaskFixture -Root $temporaryRoot -Issue 998 -Autonomy ship -Branch 'crew/998-failing' -Scope @('src/services/query/models.py') -Status 'BLOCKED: focused check fails'
    Write-TaskFixture -Root $temporaryRoot -Issue 997 -Autonomy scout -Branch 'crew/997-scout' -Scope @('research/crew') -ScoutReport
    Write-Utf8 (Join-Path $temporaryRoot '.crew\events.log') "2026-08-28 07:01:00Z | crew/999 | PR_READY_FOR_REVIEW | checks green`n2026-08-28 07:02:00Z | crew/997 | SCOUT_REPORT_READY | report present`n"

    $candidate = [ordered]@{ schemaVersion = 1; candidates = @(
        [ordered]@{ issue = 1001; type = 'ship'; goal = 'Conflicts with settings'; filesInScope = @('config/settings.yaml'); planStatus = 'approved'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/gaps.md'; heading = '## Settings'; label = 'G-SETTINGS'; excerpt = 'A durable settings gap.' } },
        [ordered]@{ issue = 1002; type = 'scout'; goal = 'Clear research candidate'; filesInScope = @('research/crew'); planStatus = 'approved'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/gaps.md'; heading = '## Research'; label = 'G-RESEARCH'; excerpt = 'A durable research gap.' } },
        [ordered]@{ issue = 1003; type = 'ship'; goal = 'Needs plan'; filesInScope = @('docs/how-to/operate.md'); planStatus = 'proposed'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/gaps.md'; heading = '## Plan'; label = 'G-PLAN'; excerpt = 'Plan approval is absent.' } }
    ) }
    Write-Utf8 (Join-Path $temporaryRoot '.crew\candidates.json') ($candidate | ConvertTo-Json -Depth 5)

    $bin = Join-Path $temporaryRoot 'bin'
    New-Item -ItemType Directory -Path $bin -Force | Out-Null
    $fakeGh = @'
@echo off
echo %* | findstr /c:"crew/999-green" >nul
if not errorlevel 1 (
  echo {"number":999,"state":"OPEN","url":"https://example.test/pr/999","reviewDecision":"REVIEW_REQUIRED","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}]}
  exit /b 0
)
echo %* | findstr /c:"crew/998-failing" >nul
if not errorlevel 1 (
  echo {"number":998,"state":"OPEN","url":"https://example.test/pr/998","reviewDecision":"","statusCheckRollup":[{"status":"COMPLETED","conclusion":"FAILURE"}]}
  exit /b 0
)
exit /b 1
'@
    $fakeGhPath = Join-Path $bin 'gh.cmd'
    Write-Utf8 $fakeGhPath $fakeGh

    $data = (& $reportScript -RepoRoot $temporaryRoot -Format data -GitHubCommand $fakeGhPath | ConvertFrom-Json)
    Assert-True (@($data.ActiveTasks).Count -eq 3) 'Every active task must appear exactly once.'
    Assert-True ([bool]($data.MaintainerActions -match 'review PR #999')) 'Green review-required PR must produce a review action.'
    Assert-True ([bool]($data.MaintainerActions -match 'failing checks on PR #998')) 'Failed checks must produce an action.'
    Assert-True ([bool]($data.MaintainerActions -match 'durable scout report')) 'Scout report handoff must produce an action.'
    Assert-True ([bool]($data.Risks -match 'BLOCKED: focused check fails')) 'Blocked worker status must be a risk.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1001))[0].Compatibility -eq 'waiting') 'settings collision must wait.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1002))[0].Compatibility -eq 'dispatchable') 'clear candidate must be dispatchable.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1003))[0].Compatibility -eq 'waiting') 'unapproved candidate must wait.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1002))[0].Evidence.Label -eq 'G-RESEARCH') 'Evidence label must survive into payload.'

    $markdown = & $reportScript -RepoRoot $temporaryRoot -Format markdown -GitHubCommand $fakeGhPath
    $html = & $reportScript -RepoRoot $temporaryRoot -Format html -GitHubCommand $fakeGhPath
    foreach ($needle in @('#999', '#998', '#997', '#1001', '#1002', '#1003', 'G-RESEARCH')) {
        Assert-True ($markdown -match [regex]::Escape($needle)) "Markdown misses $needle."
        Assert-True ($html -match [regex]::Escape($needle)) "HTML misses $needle."
    }
    Assert-True ($html -match 'Crew progress report') 'HTML must be rendered from the static report template.'

    Remove-Item -LiteralPath (Join-Path $temporaryRoot '.crew\candidates.json')
    $noCandidates = (& $reportScript -RepoRoot $temporaryRoot -Format data -GitHubCommand $fakeGhPath | ConvertFrom-Json)
    Assert-True ($noCandidates.EmptyStates.Candidates -eq 'No candidate record exists.') 'Missing candidate record must have an explicit empty state.'
    Write-Utf8 (Join-Path $temporaryRoot '.crew\candidates.json') '{ invalid json'
    $malformed = (& $reportScript -RepoRoot $temporaryRoot -Format data -GitHubCommand $fakeGhPath | ConvertFrom-Json)
    Assert-True ([bool]($malformed.DataWarnings -match 'Candidate record is malformed')) 'Malformed candidate record must produce a warning.'

    Write-Output 'crew progress report probes passed'
}
finally {
    $env:PATH = $oldPath
    if (Test-Path -LiteralPath $temporaryRoot) { Remove-Item -LiteralPath $temporaryRoot -Recurse -Force }
}
