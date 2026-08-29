# crew_pr_review.ps1 - publish and verify one independent crew PR review.
# The mate/reviewer supplies the judgment; this adapter owns GitHub side effects
# and returns a durable receipt instead of allowing a prose-only completion.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][int]$Pr,
    [Parameter(Mandatory)][ValidateSet('passing', 'required-fixes')][string]$Verdict,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$Summary,
    # Optional JSON: { "findings": [{ "body": "...", "path": "...", "line": 42, "side": "RIGHT" }] }
    [string]$FindingsPath,
    [switch]$WhatIfMode,
    [string]$RepoRoot,
    # Test seam; defaults to the authenticated GitHub CLI in normal use.
    [string]$GitHubCommand = 'gh'
)

$ErrorActionPreference = 'Stop'
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location $RepoRoot

function Invoke-CrewGitHub {
    param([string[]]$Arguments, [string]$FailureMessage)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $raw = & $GitHubCommand @Arguments 2>$null }
    finally { $ErrorActionPreference = $oldPreference }
    if ($LASTEXITCODE -ne 0 -or -not $raw) { throw $FailureMessage }
    return ($raw -join "`n")
}

function Read-CrewReviewFindings {
    param([string]$Path)
    if (-not $Path) { return @() }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Findings file not found: $Path" }
    try { $document = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
    catch { throw "Findings file is not valid JSON: $($_.Exception.Message)" }
    if ($null -eq $document.findings) { throw 'Findings JSON must contain a findings array.' }

    $comments = @()
    foreach ($finding in @($document.findings)) {
        if (-not $finding.body -or -not $finding.path -or $null -eq $finding.line -or -not $finding.side) {
            throw 'Each inline finding requires body, path, line, and side.'
        }
        $line = 0
        if (-not [int]::TryParse([string]$finding.line, [ref]$line) -or $line -lt 1) {
            throw "Inline finding line must be a positive integer: $($finding.line)"
        }
        $side = ([string]$finding.side).ToUpperInvariant()
        if ($side -notin @('LEFT', 'RIGHT')) { throw "Inline finding side must be LEFT or RIGHT: $($finding.side)" }
        $comments += [ordered]@{ body = [string]$finding.body; path = [string]$finding.path; line = $line; side = $side }
    }
    return $comments
}

$prRaw = Invoke-CrewGitHub -Arguments @('pr', 'view', "$Pr", '--json', 'headRefOid,url') `
    -FailureMessage "Unable to read PR #$Pr and its current head SHA."
try { $prInfo = $prRaw | ConvertFrom-Json } catch { throw "PR #$Pr metadata was not valid JSON." }
if (-not $prInfo.headRefOid -or -not $prInfo.url) { throw "PR #$Pr metadata is incomplete (headRefOid and url are required)." }

$repoRaw = Invoke-CrewGitHub -Arguments @('repo', 'view', '--json', 'nameWithOwner') `
    -FailureMessage 'Unable to determine the current GitHub repository.'
try { $repoInfo = $repoRaw | ConvertFrom-Json } catch { throw 'Repository metadata was not valid JSON.' }
if (-not $repoInfo.nameWithOwner) { throw 'Repository metadata has no nameWithOwner.' }

$comments = @(Read-CrewReviewFindings -Path $FindingsPath)
$event = if ($Verdict -eq 'passing') { 'COMMENT' } else { 'REQUEST_CHANGES' }
$expectedState = if ($Verdict -eq 'passing') { 'COMMENTED' } else { 'CHANGES_REQUESTED' }
$body = if ($Verdict -eq 'passing') {
    "/code-review passing verdict`n`nReviewed head: $($prInfo.headRefOid)`n`n$Summary"
} else {
    "/code-review required fixes`n`nReviewed head: $($prInfo.headRefOid)`n`n$Summary"
}
$payload = [ordered]@{ commit_id = [string]$prInfo.headRefOid; body = $body; event = $event; comments = $comments }

if ($WhatIfMode) {
    [pscustomobject]@{
        SchemaVersion = 1; Pr = $Pr; PrUrl = $prInfo.url; HeadSha = $prInfo.headRefOid
        Verdict = $Verdict; Event = $event; InlineCommentCount = @($comments).Count; WouldPublish = $true
    } | ConvertTo-Json -Depth 5
    exit 0
}

$payloadPath = Join-Path ([IO.Path]::GetTempPath()) ("crew-pr-review-" + [guid]::NewGuid().ToString() + '.json')
try {
    [IO.File]::WriteAllText($payloadPath, ($payload | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    $reviewRaw = Invoke-CrewGitHub -Arguments @('api', '--method', 'POST', "repos/$($repoInfo.nameWithOwner)/pulls/$Pr/reviews", '--input', $payloadPath) `
        -FailureMessage "GitHub did not publish the $Verdict review for PR #$Pr."
}
finally {
    if (Test-Path -LiteralPath $payloadPath) { Remove-Item -LiteralPath $payloadPath -Force }
}
try { $review = $reviewRaw | ConvertFrom-Json } catch { throw "GitHub returned invalid review JSON for PR #$Pr." }
# A worker may push between the first head lookup and review submission. A review
# against the former head is retained by GitHub but is never a current crew verdict.
$currentPrRaw = Invoke-CrewGitHub -Arguments @('pr', 'view', "$Pr", '--json', 'headRefOid') `
    -FailureMessage "Unable to re-read PR #$Pr after publishing its review."
try { $currentPrInfo = $currentPrRaw | ConvertFrom-Json } catch { throw "Current PR #$Pr metadata was not valid JSON." }
if ($currentPrInfo.headRefOid -ne $prInfo.headRefOid) {
    throw "PR #$Pr changed from reviewed head $($prInfo.headRefOid) to $($currentPrInfo.headRefOid); no current review receipt was issued."
}
if (-not $review.id -or -not $review.html_url -or -not $review.commit_id -or -not $review.state) {
    throw "GitHub review receipt for PR #$Pr is incomplete."
}
if ($review.commit_id -ne $prInfo.headRefOid) {
    throw "GitHub review receipt is for $($review.commit_id), not current head $($prInfo.headRefOid)."
}
if ($review.state -ne $expectedState) {
    throw "GitHub review receipt state is $($review.state), expected $expectedState."
}

[pscustomobject]@{
    SchemaVersion = 1
    Pr = $Pr
    PrUrl = $prInfo.url
    HeadSha = $prInfo.headRefOid
    Verdict = $Verdict
    Event = $event
    ReviewId = $review.id
    ReviewUrl = $review.html_url
    ReviewState = $review.state
    InlineCommentCount = @($comments).Count
} | ConvertTo-Json -Depth 5
