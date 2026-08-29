# test_crew_pr_review.ps1 - deterministic fixtures for GitHub review publication.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$initialLocation = (Get-Location).Path
$reviewScript = Join-Path $PSScriptRoot 'crew_pr_review.ps1'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Write-Utf8 {
    param([string]$Path, [string]$Content)
    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('crew-pr-review-' + [guid]::NewGuid())
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $fakeGh = Join-Path $root 'fake-gh.ps1'
    $logPath = Join-Path $root 'calls.jsonl'
    $fakeGhContent = @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$InvocationArgs)
$logPath = $env:CREW_REVIEW_GH_LOG
if ($InvocationArgs[0] -eq 'pr' -and $InvocationArgs[1] -eq 'view') {
    $apiWasCalled = (Test-Path -LiteralPath $logPath) -and ((Get-Content -LiteralPath $logPath -Raw) -match '"kind":"api"')
    $head = if ($env:CREW_REVIEW_GH_STALE_AFTER_PUBLISH -and $apiWasCalled) { 'head-sha-new' } else { 'head-sha-123' }
    @{ kind = 'pr-view'; args = $InvocationArgs } | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath
    [pscustomobject]@{ headRefOid = $head; url = 'https://example.test/pr/77' } | ConvertTo-Json -Compress
    exit 0
}
if ($InvocationArgs[0] -eq 'repo' -and $InvocationArgs[1] -eq 'view') {
    @{ kind = 'repo-view'; args = $InvocationArgs } | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath
    [pscustomobject]@{ nameWithOwner = 'owner/repo' } | ConvertTo-Json -Compress
    exit 0
}
if ($InvocationArgs[0] -eq 'api') {
    $inputIndex = [array]::IndexOf($InvocationArgs, '--input')
    $payload = Get-Content -LiteralPath $InvocationArgs[$inputIndex + 1] -Raw | ConvertFrom-Json
    @{ kind = 'api'; args = $InvocationArgs; payload = $payload } | ConvertTo-Json -Depth 8 -Compress | Add-Content -LiteralPath $logPath
    $state = if ($payload.event -eq 'REQUEST_CHANGES') { 'CHANGES_REQUESTED' } else { 'COMMENTED' }
    [pscustomobject]@{ id = 4242; html_url = 'https://example.test/pr/77#review-4242'; commit_id = $payload.commit_id; state = $state } | ConvertTo-Json -Compress
    exit 0
}
exit 1
'@
    Write-Utf8 -Path $fakeGh -Content $fakeGhContent
    $env:CREW_REVIEW_GH_LOG = $logPath

    $passing = (& $reviewScript -Pr 77 -Verdict passing -Summary 'Tests and verification story are sufficient.' -RepoRoot $root -GitHubCommand $fakeGh | ConvertFrom-Json)
    Assert-True ($passing.Event -eq 'COMMENT' -and $passing.ReviewState -eq 'COMMENTED') 'Passing review did not return the expected event/state receipt.'
    Assert-True ($passing.HeadSha -eq 'head-sha-123' -and $passing.InlineCommentCount -eq 0) 'Passing receipt misses current-head or comment-count evidence.'
    $passingCall = @(Get-Content -LiteralPath $logPath | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object kind -eq 'api')[0]
    Assert-True ($passingCall.payload.event -eq 'COMMENT') 'Passing review payload must use COMMENT, not approval.'
    Assert-True ($passingCall.payload.commit_id -eq 'head-sha-123') 'Passing review payload must bind to the current head SHA.'
    Assert-True ($passingCall.payload.body -match '/code-review passing verdict') 'Passing review payload lacks the durable verdict marker.'
    Assert-True ($passingCall.payload.body -match 'Reviewed head: head-sha-123') 'Passing review payload lacks its reviewed-head marker.'

    $findingsPath = Join-Path $root 'findings.json'
    Write-Utf8 -Path $findingsPath -Content '{"findings":[{"body":"Required: handle the empty input path.","path":"src/example.py","line":42,"side":"RIGHT"}]}'
    $required = (& $reviewScript -Pr 77 -Verdict required-fixes -Summary 'One required correctness fix.' -FindingsPath $findingsPath -RepoRoot $root -GitHubCommand $fakeGh | ConvertFrom-Json)
    Assert-True ($required.Event -eq 'REQUEST_CHANGES' -and $required.ReviewState -eq 'CHANGES_REQUESTED') 'Required-fixes review did not return the expected event/state receipt.'
    Assert-True ($required.InlineCommentCount -eq 1) 'Required-fixes receipt has the wrong inline-comment count.'
    $apiCalls = @(Get-Content -LiteralPath $logPath | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object kind -eq 'api')
    $requiredCall = $apiCalls[1]
    Assert-True ($requiredCall.payload.event -eq 'REQUEST_CHANGES') 'Required-fixes review payload must request changes.'
    Assert-True ($requiredCall.payload.comments[0].path -eq 'src/example.py' -and $requiredCall.payload.comments[0].line -eq 42 -and $requiredCall.payload.comments[0].side -eq 'RIGHT') 'Required-fixes inline finding was not preserved.'
    Assert-True ($requiredCall.payload.body -match '/code-review required fixes') 'Required-fixes payload lacks the durable verdict marker.'

    # A push after review submission makes the review stale. The publisher must
    # withhold a receipt so the mate cannot treat that verdict as current.
    Set-Content -LiteralPath $logPath -Value ''
    $env:CREW_REVIEW_GH_STALE_AFTER_PUBLISH = '1'
    $staleRejected = $false
    try { & $reviewScript -Pr 77 -Verdict passing -Summary 'Will become stale.' -RepoRoot $root -GitHubCommand $fakeGh | Out-Null }
    catch { $staleRejected = $_.Exception.Message -match 'changed from reviewed head' }
    Remove-Item Env:CREW_REVIEW_GH_STALE_AFTER_PUBLISH -ErrorAction SilentlyContinue
    Assert-True $staleRejected 'A PR head change after publication must reject the review receipt.'

    Write-Output 'crew PR review probes passed'
}
finally {
    Set-Location -LiteralPath $initialLocation
    Remove-Item Env:CREW_REVIEW_GH_LOG -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
