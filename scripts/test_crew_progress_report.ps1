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
    param(
        [string]$Root, [int]$Issue, [string]$Autonomy, [string]$Branch, [string[]]$Scope,
        [string]$Status = '', [string]$Goal = 'Fixture goal', [hashtable]$Evidence, [switch]$ScoutReport,
        [string]$NmHeadSha = $null
    )
    $crew = Join-Path $Root '.crew'
    $worktree = Join-Path $Root "worktrees\IHA-$Issue"
    New-Item -ItemType Directory -Path $worktree -Force | Out-Null
    $brief = Join-Path $crew "$Issue-brief.md"
    $evidenceSection = if ($Evidence) {
        "`n`n## Evidence`n`n- **Source:** $($Evidence.Source)`n- **Heading:** $($Evidence.Heading)`n- **Label:** $($Evidence.Label)`n- **Finding:** $($Evidence.Finding)"
    } else { '' }
    Write-Utf8 $brief ("# Brief`n`n## Goal`n`n$Goal$evidenceSection`n`n## Files in scope`n" + (($Scope | ForEach-Object { "- $_" }) -join "`n") + "`n`n## Out of scope`n- none`n")
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
    # Write a no-mistakes receipt when a head SHA is supplied.
    if ($NmHeadSha) {
        $nmReceipt = [ordered]@{
            head_sha = $NmHeadSha
            steps = @('review', 'test', 'lint')
            completedUtc = '2026-08-28T07:00:00Z'
        }
        Write-Utf8 (Join-Path $crew "$Issue-no-mistakes.json") ($nmReceipt | ConvertTo-Json)
    }
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("crew-progress-report-" + [guid]::NewGuid())
$oldPath = $env:PATH
try {
    New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
    Write-Utf8 (Join-Path $temporaryRoot '.lavish\part3-ingestion-research.html') '<html>G1</html>'
    Write-Utf8 (Join-Path $temporaryRoot 'research\crew\gaps.md') '# Gaps'
    Write-TaskFixture -Root $temporaryRoot -Issue 999 -Autonomy ship -Branch 'crew/999-green' -Scope @('config/settings.yaml') -Status 'WORKING: tests complete' -Goal 'Add raw-layer change detection.' -Evidence @{ Source = '.lavish/part3-ingestion-research.html'; Heading = '## Gap register'; Label = 'G1'; Finding = 'Hash-compare and change counters are needed.' }
    Write-TaskFixture -Root $temporaryRoot -Issue 998 -Autonomy ship -Branch 'crew/998-failing' -Scope @('src/services/query/models.py') -Status 'BLOCKED: focused check fails'
    Write-TaskFixture -Root $temporaryRoot -Issue 997 -Autonomy scout -Branch 'crew/997-scout' -Scope @('research/crew') -ScoutReport
    Write-TaskFixture -Root $temporaryRoot -Issue 996 -Autonomy ship -Branch 'crew/996-merged' -Scope @('docs/crew.md') -Goal 'Publish the reviewed crew report.' -Evidence @{ Source = 'research/crew/996-plan.md'; Heading = '## Approved plan'; Label = 'P996'; Finding = 'The approved plan requires this report.' } -NmHeadSha 'merged-head-996'
    Write-TaskFixture -Root $temporaryRoot -Issue 995 -Autonomy ship -Branch 'crew/995-merged-without-evidence' -Scope @('docs/crew.md')
    Write-TaskFixture -Root $temporaryRoot -Issue 994 -Autonomy ship -Branch 'crew/994-current-nm' -Scope @('docs/crew.md') -Goal 'Await maintainer approval after the current no-mistakes pass.' -NmHeadSha 'current-head-994'
    Write-TaskFixture -Root $temporaryRoot -Issue 993 -Autonomy ship -Branch 'crew/993-approved-without-nm' -Scope @('docs/crew.md') -Goal 'Require a no-mistakes pass even after a maintainer approval.'
    Write-TaskFixture -Root $temporaryRoot -Issue 992 -Autonomy ship -Branch 'crew/992-stalled' -Scope @('docs/crew.md') -Goal 'Stalled worker probe.'
    Write-Utf8 (Join-Path $temporaryRoot '.crew\992-heartbeat.json') '{"updatedAtUtc":"2026-08-01T00:00:00Z","phase":"implementing"}'
    Write-Utf8 (Join-Path $temporaryRoot '.crew\events.log') "2026-08-28 07:01:00Z | crew/999 | PR_READY_FOR_REVIEW | checks green`n2026-08-28 07:02:00Z | crew/997 | SCOUT_REPORT_READY | report present`n"

    $candidate = [ordered]@{ schemaVersion = 1; candidates = @(
        [ordered]@{ issue = 1001; type = 'ship'; goal = 'Conflicts with settings'; filesInScope = @('config/settings.yaml'); planStatus = 'approved'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/gaps.md'; heading = '## Settings'; label = 'G-SETTINGS'; excerpt = 'A durable settings gap.' } },
        [ordered]@{ issue = 1002; type = 'scout'; goal = 'Clear research candidate'; filesInScope = @('research/crew'); planStatus = 'approved'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/gaps.md'; heading = '## Research'; label = 'G-RESEARCH'; excerpt = 'A durable research gap.' } },
        [ordered]@{ issue = 1003; type = 'ship'; goal = 'Needs plan'; filesInScope = @('docs/how-to/operate.md'); planStatus = 'proposed'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/gaps.md'; heading = '## Plan'; label = 'G-PLAN'; excerpt = 'Plan approval is absent.' } },
        [ordered]@{ issue = 1004; type = 'ship'; goal = 'Missing source'; filesInScope = @('docs/how-to/operate.md'); planStatus = 'approved'; compatibility = 'clear'; evidence = [ordered]@{ source = 'research/crew/missing.md'; heading = '## Missing'; label = 'G-MISSING'; excerpt = 'This source is absent.' } }
    ) }
    Write-Utf8 (Join-Path $temporaryRoot '.crew\candidates.json') ($candidate | ConvertTo-Json -Depth 5)

    $bin = Join-Path $temporaryRoot 'bin'
    New-Item -ItemType Directory -Path $bin -Force | Out-Null
    $fakeGh = @'
@echo off
echo %* | findstr /c:"repo view" >nul
if not errorlevel 1 (
  echo {"nameWithOwner":"owner/repo"}
  exit /b 0
)
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
echo %* | findstr /c:"crew/995-merged-without-evidence" >nul
if not errorlevel 1 (
  echo {"number":995,"state":"MERGED","url":"https://example.test/pr/995","headRefOid":"current-head-995","reviewDecision":"","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}]}
  exit /b 0
)
echo %* | findstr /c:"crew/994-current-nm" >nul
if not errorlevel 1 (
  echo {"number":994,"state":"OPEN","url":"https://example.test/pr/994","headRefOid":"current-head-994","reviewDecision":"REVIEW_REQUIRED","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}]}
  exit /b 0
)
echo %* | findstr /c:"crew/993-approved-without-nm" >nul
if not errorlevel 1 (
  echo {"number":993,"state":"OPEN","url":"https://example.test/pr/993","headRefOid":"current-head-993","reviewDecision":"APPROVED","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}]}
  exit /b 0
)
echo %* | findstr /c:"crew/996-merged" >nul
if not errorlevel 1 (
  echo {"number":996,"state":"MERGED","url":"https://example.test/pr/996","headRefOid":"merged-head-996","reviewDecision":"","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"reviews":[{"state":"APPROVED","authorAssociation":"OWNER","body":"Maintainer approval"}]}
  exit /b 0
)
exit /b 1
'@
    $fakeGhPath = Join-Path $bin 'gh.cmd'
    Write-Utf8 $fakeGhPath $fakeGh

    $data = (& $reportScript -RepoRoot $temporaryRoot -Format data -GitHubCommand $fakeGhPath | ConvertFrom-Json)
    Assert-True (@($data.ActiveTasks).Count -eq 6) 'Every non-merged task must appear exactly once.'
    Assert-True (@($data.ActiveTasks | Where-Object Issue -in @(995, 996)).Count -eq 0) 'A merged PR must not remain active.'
    Assert-True (@($data.FullyMergedPrs).Count -eq 1 -and $data.FullyMergedPrs[0].Issue -eq 996) 'Only PRs with merged, maintainer-approval, and no-mistakes evidence belong in fully merged PRs.'
    Assert-True ([bool]($data.DataWarnings -match '#995: PR #995 is merged but lacks durable')) 'Merged PRs without qualifying evidence must remain visible as a warning.'
    Assert-True ([bool]($data.MaintainerActions -match 'no-mistakes pipeline for PR #999')) 'Green PR without a no-mistakes receipt must request the gate.'
    Assert-True ((@($data.ActiveTasks | Where-Object Issue -eq 999))[0].Pr.Review -eq 'No-mistakes gate required') 'A green PR without a current receipt must not be summarized as awaiting maintainer approval.'
    Assert-True ([bool]($data.MaintainerActions -match 'PR #994.*maintainer approval')) 'Only a green PR with a current no-mistakes pass may request maintainer approval.'
    Assert-True ((@($data.ActiveTasks | Where-Object Issue -eq 994))[0].Pr.Review -eq 'Awaiting maintainer approval') 'A current no-mistakes pass must surface the correct maintainer-approval summary.'
    Assert-True ([bool]($data.MaintainerActions -match 'no-mistakes pipeline for PR #993')) 'A prior maintainer approval must not bypass the no-mistakes gate.'
    Assert-True ((@($data.ActiveTasks | Where-Object Issue -eq 993))[0].Pr.Review -eq 'No-mistakes gate required') 'An approved PR without a current no-mistakes receipt must be summarized as needing the gate.'
    Assert-True ([bool]($data.MaintainerActions -match 'failing checks on PR #998')) 'Failed checks must produce an action.'
    Assert-True ([bool]($data.MaintainerActions -match 'durable scout report')) 'Scout report handoff must produce an action.'
    Assert-True ([bool]($data.Risks -match 'BLOCKED: focused check fails')) 'Blocked worker status must be a risk.'
    Assert-True ([bool]($data.Risks -match '992.*worker heartbeat stale')) 'A stale heartbeat must surface as a risk.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1001))[0].Compatibility -eq 'waiting') 'settings collision must wait.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1002))[0].Compatibility -eq 'dispatchable') 'clear candidate must be dispatchable.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1003))[0].Compatibility -eq 'waiting') 'unapproved candidate must wait.'
    Assert-True (@($data.NextCompatibleTasks | Where-Object Issue -eq 1004).Count -eq 0) 'A candidate with a missing evidence source must be ignored.'
    Assert-True ([bool]($data.DataWarnings -match 'missing durable evidence source: research/crew/missing.md')) 'A missing candidate evidence source must produce a warning.'
    Assert-True ((@($data.NextCompatibleTasks | Where-Object Issue -eq 1002))[0].Evidence.Label -eq 'G-RESEARCH') 'Candidate evidence label must survive into payload.'
    Assert-True ((@($data.ActiveTasks | Where-Object Issue -eq 999))[0].Evidence.Label -eq 'G1') 'Active-task research evidence must take precedence over the brief fallback.'
    Remove-Item -LiteralPath (Join-Path $temporaryRoot '.lavish\part3-ingestion-research.html')
    $missingEvidence = (& $reportScript -RepoRoot $temporaryRoot -Format data -GitHubCommand $fakeGhPath | ConvertFrom-Json)
    Assert-True ((@($missingEvidence.ActiveTasks | Where-Object Issue -eq 999))[0].Evidence.Label -eq 'Task brief') 'A missing evidence source must fall back to the durable task brief.'
    Write-Utf8 (Join-Path $temporaryRoot '.lavish\part3-ingestion-research.html') '<html>G1</html>'

    $defaultReport = & $reportScript -RepoRoot $temporaryRoot -GitHubCommand $fakeGhPath
    $markdown = & $reportScript -RepoRoot $temporaryRoot -Format markdown -GitHubCommand $fakeGhPath
    $html = & $reportScript -RepoRoot $temporaryRoot -Format html -GitHubCommand $fakeGhPath
    foreach ($needle in @('#999', '#998', '#997', '#995', '#996', '#992', '#1001', '#1002', '#1003', 'G-RESEARCH', 'G1', 'Evidence / source')) {
        Assert-True ($markdown -match [regex]::Escape($needle)) "Markdown misses $needle."
        Assert-True ($html -match [regex]::Escape($needle)) "HTML misses $needle."
    }
    Assert-True ($defaultReport -match '^# Crew progress report') 'Markdown must be the default format.'
    Assert-True ($markdown -match '\| Issue \| Task \| Goal \| PR state \| Evidence / source \|') 'Active tasks must render as a Markdown table.'
    Assert-True ($markdown -notmatch '## Landing order') 'Landing order must not be rendered.'
    Assert-True ($html -match 'Crew progress report') 'HTML must be rendered from the static report template.'
    Assert-True ($html -notmatch 'Landing order') 'HTML must not render landing order.'

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
