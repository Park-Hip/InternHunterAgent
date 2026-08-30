# crew_no_mistakes.ps1 - parse and validate a no-mistakes pipeline receipt.
# A no-mistakes receipt is a durable, head-bound JSON file written by the
# no-mistakes pipeline after it completes all local gates (review, test, document,
# lint) and publishes the branch + PR. The receipt's `head_sha` must match the
# current branch head; stale receipts for older SHAs are rejected so a ship
# cannot be escalated on a superseded pass.
#
# The pipeline also embeds an HTML comment in the last pushed commit message:
#   <!-- no-mistakes-pipeline-attestation:v1 {"head_sha":"...","steps":[...]} -->
# This adapter accepts either the standalone receipt file or the embedded
# attestation in the commit body.

[CmdletBinding()]
param(
    # Path to the no-mistakes receipt JSON file. When omitted the script looks
    # for .no-mistakes-receipt.json in the repo root.
    [string]$ReceiptPath,
    # Branch whose head SHA must match the receipt. Defaults to the current branch.
    [string]$Branch,
    # Dry-run: validate the receipt format without writing state.
    [switch]$WhatIfMode,
    [string]$RepoRoot
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $RepoRoot = Split-Path -Parent $scriptDir
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Set-Location $RepoRoot

function Get-CrewNoMistakesDefaultReceiptPath {
    return Join-Path $RepoRoot '.no-mistakes-receipt.json'
}

function Get-CrewCurrentHeadSha {
    param([string]$Branch)
    $target = if ($Branch) { $Branch } else { (git rev-parse --abbrev-ref HEAD) }
    $sha = git rev-parse "$target" 2>$null
    if (-not $sha) { throw "Cannot resolve head SHA for branch '$target'." }
    return $sha.Trim()
}

function Read-CrewNoMistakesReceipt {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "No-mistakes receipt not found at '$Path'."
    }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw
    }
    catch {
        throw "Cannot read receipt at '$Path': $($_.Exception.Message)"
    }
    try {
        $receipt = $raw | ConvertFrom-Json
    }
    catch {
        throw "Receipt at '$Path' is not valid JSON: $($_.Exception.Message)"
    }
    if (-not $receipt.head_sha) { throw "Receipt at '$Path' is missing required field 'head_sha'." }
    if (-not $receipt.steps) { throw "Receipt at '$Path' is missing required field 'steps'." }
    return $receipt
}

function Parse-CrewNoMistakesAttestation {
    param([string]$CommitBody)
    # Match the HTML comment attestation embedded in the last pushed commit.
    $pattern = '<!--\s*no-mistakes-pipeline-attestation:v1\s+([\s\S]*?)\s*-->'
    $match = [regex]::Match($CommitBody, $pattern)
    if (-not $match.Success) { return $null }
    try {
        return $match.Groups[1].Value.Trim() | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Assert-CrewNoMistakesReceiptIsCurrent {
    param(
        [Parameter(Mandatory)][string]$Receipt,
        [Parameter(Mandatory)][string]$CurrentSha
    )
    $parsed = $Receipt | ConvertFrom-Json
    if ($parsed.head_sha -ne $CurrentSha) {
        throw "No-mistakes receipt head_sha '$($parsed.head_sha)' does not match current head '$CurrentSha'. Stale receipt rejected."
    }
    return $parsed
}

$receiptPath = if ($ReceiptPath) { $ReceiptPath } else { Get-CrewNoMistakesDefaultReceiptPath }
$currentSha = Get-CrewCurrentHeadSha -Branch $Branch

if (Test-Path -LiteralPath $receiptPath) {
    $receipt = Read-CrewNoMistakesReceipt -Path $receiptPath
    $parsed = Assert-CrewNoMistakesReceiptIsCurrent -Receipt $receipt -CurrentSha $currentSha
    $result = [pscustomobject]@{
        SchemaVersion = 1
        Valid         = $true
        HeadSha       = $parsed.head_sha
        Steps         = $parsed.steps
        Source        = $receiptPath
    }
    if ($WhatIfMode) {
        $result.WouldPersist = $true
    }
    else {
        # Persist validated receipt as durable evidence under .crew/<issue>-no-mistakes.json
        # The issue number is extracted from the branch name.
        $issueMatch = $currentSha | Out-Null
        $branchName = if ($Branch) { $Branch } else { git rev-parse --abbrev-ref HEAD }
        $issueNum = if ($branchName -match '(?:^|/)(?:iha|crew)-?(\d+)') { $Matches[1] }
                    elseif ($branchName -match '^crew/(\d+)') { $Matches[1] }
                    else { $null }
        if ($issueNum) {
            $durablePath = Join-Path $RepoRoot ".crew\$issueNum-no-mistakes.json"
            Write-CrewUtf8File -Path $durablePath -Content ($parsed | ConvertTo-Json -Depth 4)
            $result.DurablePath = $durablePath
        }
    }
    $result | ConvertTo-Json -Depth 4
    exit 0
}

# Fallback: try parsing the attestation from the latest commit message.
$commitBody = git log -1 --format=%B 2>$null
if ($commitBody) {
    $parsed = Parse-CrewNoMistakesAttestation -CommitBody $commitBody
    if ($parsed) {
        try {
            Assert-CrewNoMistakesReceiptIsCurrent -Receipt $parsed -CurrentSha $currentSha | Out-Null
            $result = [pscustomobject]@{
                SchemaVersion = 1
                Valid         = $true
                HeadSha       = $parsed.head_sha
                Steps         = $parsed.steps
                Source        = 'commit-attestation'
            }
            if ($WhatIfMode) {
                $result.WouldPersist = $true
            }
            else {
                $branchName = if ($Branch) { $Branch } else { git rev-parse --abbrev-ref HEAD }
                $issueNum = if ($branchName -match '(?:^|/)(?:iha|crew)-?(\d+)') { $Matches[1] }
                            elseif ($branchName -match '^crew/(\d+)') { $Matches[1] }
                            else { $null }
                if ($issueNum) {
                    $durablePath = Join-Path $RepoRoot ".crew\$issueNum-no-mistakes.json"
                    Write-CrewUtf8File -Path $durablePath -Content ($parsed | ConvertTo-Json -Depth 4)
                    $result.DurablePath = $durablePath
                }
            }
            $result | ConvertTo-Json -Depth 4
            exit 0
        }
        catch {
            # Stale attestation - fall through to failure.
        }
    }
}

# No valid receipt found.
$result = [pscustomobject]@{
    SchemaVersion = 1
    Valid         = $false
    HeadSha       = $currentSha
    Source        = $null
    Error         = 'No valid no-mistakes receipt found for current head.'
}
$result | ConvertTo-Json -Depth 4
exit 1
