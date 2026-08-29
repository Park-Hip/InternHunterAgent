# test_mate_watch.ps1 - deterministic current-head review-gate probes for mate_watch.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$watchScript = Join-Path $PSScriptRoot 'mate_watch.ps1'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Write-Utf8 {
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}
function Invoke-TestGit {
    param([string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed." }
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('mate-watch-' + [guid]::NewGuid())
$oldPath = $env:PATH
$initialLocation = (Get-Location).Path
try {
    $repo = Join-Path $root 'InternHunterAgent'
    $worktree = Join-Path $root 'InternHunterAgent-worktrees\IHA-777'
    New-Item -ItemType Directory -Path $repo -Force | Out-Null
    Invoke-TestGit -Arguments @('-C', $repo, 'init', '-b', 'main')
    Invoke-TestGit -Arguments @('-C', $repo, 'config', 'user.email', 'watch-probe@example.test')
    Invoke-TestGit -Arguments @('-C', $repo, 'config', 'user.name', 'Mate Watch Probe')
    Write-Utf8 -Path (Join-Path $repo 'README.md') -Content '# Watch probe'
    Invoke-TestGit -Arguments @('-C', $repo, 'add', 'README.md')
    Invoke-TestGit -Arguments @('-C', $repo, 'commit', '-m', 'test: initialize mate watcher probe')
    New-Item -ItemType Directory -Path (Split-Path -Parent $worktree) -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $repo '.crew') -Force | Out-Null
    Invoke-TestGit -Arguments @('-C', $repo, 'worktree', 'add', $worktree, '-b', 'crew/777-watch-probe', 'main')

    $bin = Join-Path $root 'bin'
    New-Item -ItemType Directory -Path $bin -Force | Out-Null
    $fakeGh = @'
@echo off
echo %* | findstr /c:"repo view" >nul
if not errorlevel 1 (
  echo {"nameWithOwner":"owner/repo"}
  exit /b 0
)
echo %* | findstr /c:"/reviews" >nul
if not errorlevel 1 (
  if "%CREW_WATCH_SKILL_PASS%"=="1" (
    echo [[{"commit_id":"head-777","state":"COMMENTED","body":"/code-review passing verdict\nReviewed head: head-777"}]]
  ) else (
    echo [[]]
  )
  exit /b 0
)
if "%CREW_WATCH_PENDING%"=="1" (
  echo {"number":777,"state":"OPEN","headRefOid":"head-777","reviewDecision":"REVIEW_REQUIRED","statusCheckRollup":[{"status":"IN_PROGRESS","conclusion":""}],"comments":[],"reviews":[]}
) else if "%CREW_WATCH_APPROVED%"=="1" (
  echo {"number":777,"state":"OPEN","headRefOid":"head-777","reviewDecision":"APPROVED","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"comments":[],"reviews":[{"state":"APPROVED","body":"Maintainer approval"}]}
) else if "%CREW_WATCH_SKILL_PASS%"=="1" (
  echo {"number":777,"state":"OPEN","headRefOid":"head-777","reviewDecision":"REVIEW_REQUIRED","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"comments":[],"reviews":[{"state":"COMMENTED","body":"/code-review passing verdict\nReviewed head: head-777"}]}
) else (
  echo {"number":777,"state":"OPEN","headRefOid":"head-777","reviewDecision":"REVIEW_REQUIRED","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"comments":[],"reviews":[]}
)
'@
    Write-Utf8 -Path (Join-Path $bin 'gh.cmd') -Content $fakeGh
    $env:PATH = "$bin;$oldPath"

    $env:CREW_WATCH_PENDING = '1'
    & $watchScript -Once -NoToast -RepoRoot $repo | Out-Null
    Remove-Item Env:CREW_WATCH_PENDING -ErrorAction SilentlyContinue
    & $watchScript -Once -NoToast -RepoRoot $repo | Out-Null
    $firstEvents = Get-Content -LiteralPath (Join-Path $repo '.crew\events.log') -Raw
    Assert-True ($firstEvents -match 'independent current-head /code-review verdict required') "Green PR without a current verdict must request the independent review first. Events: $firstEvents"

    $env:CREW_WATCH_SKILL_PASS = '1'
    & $watchScript -Once -NoToast -RepoRoot $repo | Out-Null
    $secondEvents = Get-Content -LiteralPath (Join-Path $repo '.crew\events.log') -Raw
    Assert-True ($secondEvents -match 'current /code-review verdict; awaiting maintainer approval') 'Only a current passing verdict may advance the watcher to maintainer approval.'

    Remove-Item Env:CREW_WATCH_SKILL_PASS -ErrorAction SilentlyContinue
    $env:CREW_WATCH_APPROVED = '1'
    & $watchScript -Once -NoToast -RepoRoot $repo | Out-Null
    $thirdEvents = Get-Content -LiteralPath (Join-Path $repo '.crew\events.log') -Raw
    Assert-True (($thirdEvents -split "`r?`n" | Where-Object { $_ -match 'independent current-head /code-review verdict required' }).Count -ge 2) 'A maintainer-approved PR without the independent verdict must still request that verdict.'

    # Heartbeat / stalled-worker scenario. A heartbeat older than the threshold must
    # emit exactly one WORKER_STALLED; a fresh heartbeat clears it without a repeat;
    # a second stale beat re-arms the event.
    $hbPath = Join-Path $repo '.crew\777-heartbeat.json'
    Write-Utf8 -Path $hbPath -Content ('{"updatedAtUtc":"' + (Get-Date).ToUniversalTime().AddMinutes(-20).ToString('o') + '","phase":"implementing"}')
    & $watchScript -Once -NoToast -RepoRoot $repo -StalledAfterSec 60 -IdleSweeps 120 | Out-Null
    $stallEvents = Get-Content -LiteralPath (Join-Path $repo '.crew\events.log') -Raw
    Assert-True ($stallEvents -match 'WORKER_STALLED') 'A heartbeat older than the threshold must emit WORKER_STALLED.'

    Write-Utf8 -Path $hbPath -Content ('{"updatedAtUtc":"' + (Get-Date).ToUniversalTime().ToString('o') + '","phase":"tests-green"}')
    & $watchScript -Once -NoToast -RepoRoot $repo -StalledAfterSec 60 -IdleSweeps 120 | Out-Null
    $clearedEvents = Get-Content -LiteralPath (Join-Path $repo '.crew\events.log') -Raw
    Assert-True (@($clearedEvents -split "`r?`n" | Where-Object { $_ -match 'WORKER_STALLED' }).Count -eq 1) 'A fresh heartbeat must clear the stall without re-emitting.'

    Write-Utf8 -Path $hbPath -Content ('{"updatedAtUtc":"' + (Get-Date).ToUniversalTime().AddMinutes(-20).ToString('o') + '","phase":"implementing"}')
    & $watchScript -Once -NoToast -RepoRoot $repo -StalledAfterSec 60 -IdleSweeps 120 | Out-Null
    $rearmedEvents = Get-Content -LiteralPath (Join-Path $repo '.crew\events.log') -Raw
    Assert-True (@($rearmedEvents -split "`r?`n" | Where-Object { $_ -match 'WORKER_STALLED' }).Count -eq 2) 'A stall that recurs after a clear must re-emit WORKER_STALLED.'

    Write-Output 'mate watch probes passed' 
}
finally {
    Set-Location -LiteralPath $initialLocation
    Remove-Item Env:CREW_WATCH_PENDING -ErrorAction SilentlyContinue
    Remove-Item Env:CREW_WATCH_SKILL_PASS -ErrorAction SilentlyContinue
    Remove-Item Env:CREW_WATCH_APPROVED -ErrorAction SilentlyContinue
    $env:PATH = $oldPath
    if (Test-Path -LiteralPath $repo) {
        & git -C $repo worktree remove --force $worktree 2>$null
        & git -C $repo worktree prune 2>$null
    }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
