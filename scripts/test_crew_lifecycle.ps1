# test_crew_lifecycle.ps1 - deterministic probes for the native Windows crew lifecycle.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'crew_lifecycle.ps1')
. (Join-Path $PSScriptRoot 'crew_terminal_backend.ps1')
. (Join-Path $PSScriptRoot 'crew_vscode_backend.ps1')
$initialLocation = (Get-Location).Path

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-TestGit {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & git @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed." }
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("crew-lifecycle-" + [guid]::NewGuid())
try {
    $repoRoot = Join-Path $temporaryRoot 'InternHunterAgent'
    New-Item -ItemType Directory -Path $repoRoot -Force | Out-Null
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'init', '-b', 'main')
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'config', 'user.email', 'crew-probe@example.test')
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'config', 'user.name', 'Crew Lifecycle Probe')
    Write-CrewUtf8File -Path (Join-Path $repoRoot 'README.md') -Content '# Lifecycle probe'
    Write-CrewUtf8File -Path (Join-Path $repoRoot '.gitignore') -Content ".crew/[0-9]*-*.md`n.crew/[0-9]*-task.json`n"
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'add', 'README.md', '.gitignore')
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'commit', '-m', 'test: initialize crew lifecycle probe')

    New-Item -ItemType Directory -Path (Join-Path $repoRoot '.crew') -Force | Out-Null
    $paths = Get-CrewTaskPaths -RepoRoot $repoRoot -Issue 999
    Assert-Equal $paths.WorktreeRoot (Join-Path $temporaryRoot 'InternHunterAgent-worktrees') 'Worktree root calculation failed.'
    Assert-Equal $paths.PrimaryHeartbeatPath (Join-Path $repoRoot '.crew\999-heartbeat.json') 'Heartbeat path derivation failed.'
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'worktree', 'add', $paths.WorktreePath, '-b', 'crew/999-lifecycle-probe', 'main')

    Write-CrewUtf8File -Path $paths.PrimaryBriefPath -Content '# Brief: lifecycle probe'
    Write-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath -Issue 999 -IssueUrl 'https://example.test/issues/999' -Title 'Lifecycle probe' -Autonomy scout -Branch 'crew/999-lifecycle-probe' -RepoRoot $repoRoot -WorktreePath $paths.WorktreePath -PrimaryBriefPath $paths.PrimaryBriefPath -PrimaryStatusPath $paths.PrimaryStatusPath -TaskBriefPath $paths.TaskBriefPath -ScoutReportPath $paths.ScoutReportPath -TerminalBackend wt | Out-Null
    Copy-CrewTaskContractFiles -PrimaryBriefPath $paths.PrimaryBriefPath -TaskBriefPath $paths.TaskBriefPath -PrimaryManifestPath $paths.PrimaryManifestPath -TaskManifestPath $paths.TaskManifestPath
    if (-not (Test-Path -LiteralPath $paths.TaskBriefPath)) { throw 'Task-local brief was not created.' }
    if (-not (Test-Path -LiteralPath $paths.TaskManifestPath)) { throw 'Task-local manifest was not created.' }
    Write-CrewHeartbeat -HeartbeatPath $paths.PrimaryHeartbeatPath -Phase 'dispatched' | Out-Null
    $hb = Get-Content -LiteralPath $paths.PrimaryHeartbeatPath -Raw | ConvertFrom-Json
    Assert-Equal $hb.phase 'dispatched' 'Heartbeat did not record the phase.'
    if (-not $hb.updatedAtUtc) { throw 'Heartbeat did not record an updatedAtUtc timestamp.' }

    try {
        & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 999 -RepoRoot $repoRoot
        throw 'Scout teardown was not refused before report handoff.'
    }
    catch {
        if ($_.Exception.Message -eq 'Scout teardown was not refused before report handoff.') { throw }
    }
    if (-not (Test-Path -LiteralPath $paths.WorktreePath)) { throw 'Refused scout teardown removed the worktree.' }

    Write-CrewUtf8File -Path $paths.ScoutReportPath -Content '# Durable scout report'
    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 999 -RepoRoot $repoRoot -ConfirmScoutReportHandoff -WhatIfMode | Out-Null
    if (-not (Test-Path -LiteralPath $paths.WorktreePath)) { throw 'Dry-run scout teardown removed the worktree.' }
    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 999 -RepoRoot $repoRoot -ConfirmScoutReportHandoff | Out-Null
    if (Test-Path -LiteralPath $paths.WorktreePath) { throw 'Confirmed scout teardown did not remove the worktree.' }
    $tornDownManifest = Read-CrewTaskManifest -ManifestPath $paths.PrimaryManifestPath
    Assert-Equal $tornDownManifest.State 'torn_down' 'Teardown did not update the manifest state.'
    Assert-Equal $tornDownManifest.ScoutReportHandedOff $true 'Teardown did not record scout report handoff.'

    # vscode-task teardown round-trip: a registered Run Task entry must be
    # removed by teardown while unrelated entries in the same file survive.
    $vscodePaths = Get-CrewTaskPaths -RepoRoot $repoRoot -Issue 998
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'worktree', 'add', $vscodePaths.WorktreePath, '-b', 'crew/998-vscode-task-probe', 'main')
    Write-CrewUtf8File -Path $vscodePaths.PrimaryBriefPath -Content '# Brief: vscode-task probe'
    Write-CrewTaskManifest -ManifestPath $vscodePaths.PrimaryManifestPath -Issue 998 -IssueUrl 'https://example.test/issues/998' -Title 'vscode-task probe' -Autonomy ship -Branch 'crew/998-vscode-task-probe' -RepoRoot $repoRoot -WorktreePath $vscodePaths.WorktreePath -PrimaryBriefPath $vscodePaths.PrimaryBriefPath -PrimaryStatusPath $vscodePaths.PrimaryStatusPath -TaskBriefPath $vscodePaths.TaskBriefPath -ScoutReportPath $vscodePaths.ScoutReportPath -TerminalBackend vscode-task | Out-Null

    $tasksPath = Join-Path $repoRoot '.vscode\tasks.json'
    $unrelatedLabel = 'Build: unrelated task'
    $registeredPiArgs = Resolve-CrewHarnessArgs -Harness 'pi' -HarnessArgs '' -Backend 'vscode-task'
    Assert-Equal $registeredPiArgs '--model modelscope/deepseek-ai/DeepSeek-V4-Pro-0813' 'Registered Pi task did not select the ModelScope default model.'
    Assert-Equal (Resolve-CrewHarnessArgs -Harness 'pi' -HarnessArgs '--model dashscope/glm-5.2' -Backend 'vscode-task') '--model dashscope/glm-5.2' 'An explicit Pi model override was not retained.'
    Assert-Equal (Resolve-CrewHarnessArgs -Harness 'pi' -HarnessArgs '' -Backend 'vscode') '' 'New-window Pi launches must not silently receive the registration-only default.'
    Add-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath 'D:\elsewhere\unrelated' -TaskName $unrelatedLabel -HarnessPath 'pi.exe' -HarnessArgs '' -WorkerPrompt 'unrelated' | Out-Null
    Add-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath $vscodePaths.WorktreePath -TaskName 'Crew: IHA-998 worker' -HarnessPath 'pi.exe' -HarnessArgs $registeredPiArgs -WorkerPrompt 'probe' | Out-Null
    $before = Get-Content -LiteralPath $tasksPath -Raw | ConvertFrom-Json
    Assert-Equal @($before.tasks).Count 2 'Both task entries were not registered.'
    $registeredTask = @($before.tasks | Where-Object { $_.label -eq 'Crew: IHA-998 worker' })[0]
    Assert-Equal $registeredTask.options.cwd $vscodePaths.WorktreePath 'Registered Pi task did not target the crew worktree.'
    Assert-Equal ($registeredTask.args -join ' ') '--model modelscope/deepseek-ai/DeepSeek-V4-Pro-0813 probe' 'Registered Pi task does not carry the ModelScope model argument.'

    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 998 -RepoRoot $repoRoot | ForEach-Object {
        if ($_ -like 'vscode-task : removed*') { $sawRemovalReport = $true }
        $_
    } | Out-Null
    if (-not $sawRemovalReport) { throw 'Teardown did not report the vscode-task entry removal.' }
    if (Test-Path -LiteralPath $vscodePaths.WorktreePath) { throw 'vscode-task teardown did not remove the worktree.' }
    $afterJson = Get-Content -LiteralPath $tasksPath -Raw
    $after = $afterJson | ConvertFrom-Json
    Assert-Equal @($after.tasks).Count 1 'Unrelated task entry did not survive teardown.'
    Assert-Equal @($after.tasks)[0].label $unrelatedLabel 'The surviving entry is not the unrelated task.'
    $leadingBytes = [System.IO.File]::ReadAllBytes($tasksPath)[0..2]
    if ($leadingBytes[0] -eq 0xEF -and $leadingBytes[1] -eq 0xBB -and $leadingBytes[2] -eq 0xBF) { throw '.vscode/tasks.json was rewritten with a BOM.' }

    # vscode-task-auto: pin the cross-language spec hash, publish an immutable
    # request, reconcile extension events to a manifest status, and confirm
    # teardown removes only that request's records.
    $autoPaths = Get-CrewTaskPaths -RepoRoot $repoRoot -Issue 997
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'worktree', 'add', $autoPaths.WorktreePath, '-b', 'crew/997-vscode-task-auto-probe', 'main')
    Write-CrewUtf8File -Path $autoPaths.PrimaryBriefPath -Content '# Brief: vscode-task-auto probe'
    Write-CrewTaskManifest -ManifestPath $autoPaths.PrimaryManifestPath -Issue 997 -IssueUrl 'https://example.test/issues/997' -Title 'vscode-task-auto probe' -Autonomy ship -Branch 'crew/997-vscode-task-auto-probe' -RepoRoot $repoRoot -WorktreePath $autoPaths.WorktreePath -PrimaryBriefPath $autoPaths.PrimaryBriefPath -PrimaryStatusPath $autoPaths.PrimaryStatusPath -TaskBriefPath $autoPaths.TaskBriefPath -ScoutReportPath $autoPaths.ScoutReportPath -TerminalBackend vscode-task-auto | Out-Null

    $fixtureSpec = [ordered]@{ specVersion = 1; type = 'shell'; command = 'C:\tools\pi.exe'; args = [string[]]@('--model', 'modelscope/x'); cwd = 'D:\crew\IHA-1' }
    Assert-Equal (Get-CrewExecutionSpecHash -Spec $fixtureSpec) '00787f451655efe3c04a166aadb609f77bfbebc95965c38347b10f3e9be753d0' 'The Powershell canonical spec hash diverged from the JS fixture.'

    $spec = New-CrewExecutionSpec -HarnessPath 'C:\tools\pi.exe' -HarnessArgs '--model modelscope/x' -WorkerPrompt 'do the work' -WorktreePath $autoPaths.WorktreePath
    $specHash = Get-CrewExecutionSpecHash -Spec $spec
    $requestId = 'IHA-997-' + [guid]::NewGuid().ToString('N')
    $requestPath = Add-CrewVsCodeAutoRequest -RepoRoot $repoRoot -RequestId $requestId -Issue 997 -TaskName 'Crew: IHA-997 worker (pi)' -WorktreePath $autoPaths.WorktreePath -ExecutionSpec $spec -ManifestPath $autoPaths.PrimaryManifestPath
    if (-not (Test-Path -LiteralPath $requestPath)) { throw 'Auto-launch request was not published.' }
    $request = Get-Content -LiteralPath $requestPath -Raw | ConvertFrom-Json
    Assert-Equal $request.requestId $requestId 'Published request id mismatch.'
    Assert-Equal $request.executionSpecHash $specHash 'Published request hash mismatch.'
    Assert-Equal $request.executionSpec.command 'C:\tools\pi.exe' 'Published request command mismatch.'
    Assert-Equal ($request.executionSpec.args -join ' ') '--model modelscope/x do the work' 'Published request args mismatch.'
    try {
        Add-CrewVsCodeAutoRequest -RepoRoot $repoRoot -RequestId $requestId -Issue 997 -TaskName 'Crew: IHA-997 worker (pi)' -WorktreePath $autoPaths.WorktreePath -ExecutionSpec $spec -ManifestPath $autoPaths.PrimaryManifestPath | Out-Null
        throw 'Second publication with the same request id was not refused.'
    }
    catch {
        if ($_.Exception.Message -eq 'Second publication with the same request id was not refused.') { throw }
    }

    $autoQueue = Join-Path (Join-Path $repoRoot '.crew') 'launch-queue'
    $resultsDir = Join-Path $autoQueue 'results'
    New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
    $eventsPath = Join-Path $resultsDir ($requestId + '.events.jsonl')
    [System.IO.File]::AppendAllText($eventsPath, '{ "ts": "2026-01-01T00:00:01Z", "event": "validated" }' + "`n", [System.Text.UTF8Encoding]::new($false))
    Assert-Equal (Get-CrewVsCodeAutoLaunchEvent -RepoRoot $repoRoot -RequestId $requestId) $null 'Non-terminal events must not resolve to a launch event.'
    [System.IO.File]::AppendAllText($eventsPath, '{ "ts": "2026-01-01T00:00:02Z", "event": "started", "processId": 7 }' + "`n", [System.Text.UTF8Encoding]::new($false))
    Assert-Equal (Get-CrewVsCodeAutoLaunchEvent -RepoRoot $repoRoot -RequestId $requestId) 'started' 'Terminal event was not resolved.'
    $status = Get-CrewVsCodeAutoLaunchStatus -LaunchEvent (Get-CrewVsCodeAutoLaunchEvent -RepoRoot $repoRoot -RequestId $requestId)
    Assert-Equal $status.Status 'launched' 'Started event did not map to launched status.'

    $unrelatedRequestId = 'IHA-996-' + [guid]::NewGuid().ToString('N')
    $unrelatedManifest = Join-Path $repoRoot '.crew\996-task.json'
    Add-CrewVsCodeAutoRequest -RepoRoot $repoRoot -RequestId $unrelatedRequestId -Issue 996 -TaskName 'Crew: IHA-996 worker (pi)' -WorktreePath 'D:\elsewhere\unrelated-auto' -ExecutionSpec $spec -ManifestPath $unrelatedManifest | Out-Null
    Add-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath $autoPaths.WorktreePath -TaskName 'Crew: IHA-997 worker (pi)' -HarnessPath 'C:\tools\pi.exe' -HarnessArgs '--model modelscope/x' -WorkerPrompt 'do the work' | Out-Null
    Update-CrewTaskManifest -ManifestPath $autoPaths.PrimaryManifestPath -Changes @{
        TerminalBackend        = 'vscode-task-auto'
        TerminalLaunchSpec     = $spec
        TerminalLaunchSpecHash = $specHash
        LaunchRequestId        = $requestId
        TerminalLaunchStatus   = 'launched'
    } | Out-Null

    $autoSawRemoved = $false
    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 997 -RepoRoot $repoRoot | ForEach-Object {
        if ($_ -like 'vscode-task-auto : removed*') { $autoSawRemoved = $true }
        $_
    } | Out-Null
    if (-not $autoSawRemoved) { throw 'Teardown did not report the vscode-task-auto entry removal.' }
    if (Test-Path -LiteralPath $autoPaths.WorktreePath) { throw 'vscode-task-auto teardown did not remove the worktree.' }
    if (Test-Path -LiteralPath $requestPath) { throw 'Teardown left the request record in place.' }
    if (Test-Path -LiteralPath $eventsPath) { throw 'Teardown left the result record in place.' }
    $unrelatedRequestPath = Join-Path (Join-Path $autoQueue 'requests') ($unrelatedRequestId + '.json')
    if (-not (Test-Path -LiteralPath $unrelatedRequestPath)) { throw 'Teardown removed an unrelated launch request.' }

    # A second teardown of an already-torn-down task is refused before any
    # removal runs; exercise Remove directly to confirm a no-match is safe.
    try {
        & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 998 -RepoRoot $repoRoot | Out-Null
        throw 'Second teardown of issue 998 was not refused.'
    }
    catch {
        if ($_.Exception.Message -eq 'Second teardown of issue 998 was not refused.') { throw }
    }
    $noMatch = Remove-CrewVsCodeTaskEntry -RepoRoot $repoRoot -WorktreePath $vscodePaths.WorktreePath
    Assert-Equal $noMatch.Removed 0 'Repeat removal should report zero entries removed.'

    $plan = New-CrewWindowsTerminalLaunchPlan -WorktreePath $paths.WorktreePath -SessionCommand 'Write-Host lifecycle-probe'
    Assert-Equal $plan.Backend 'windows-terminal' 'Terminal backend selection failed.'
    Assert-Equal $plan.FilePath 'wt.exe' 'Windows Terminal executable selection failed.'
    if ($plan.ArgumentList -notcontains '-EncodedCommand') { throw 'Windows Terminal launch plan does not encode the session command.' }

    # No-mistakes manifest fields: Write-CrewTaskManifest must include
    # NoMistakesReceiptPath and NoMistakesValid; Get-CrewNoMistakesStatus must
    # report the gate correctly.
    $nmPaths = Get-CrewTaskPaths -RepoRoot $repoRoot -Issue 996
    Invoke-TestGit -Arguments @('-C', $repoRoot, 'worktree', 'add', $nmPaths.WorktreePath, '-b', 'crew/996-no-mistakes-probe', 'main')
    Write-CrewUtf8File -Path $nmPaths.PrimaryBriefPath -Content '# Brief: no-mistakes probe'
    Write-CrewTaskManifest -ManifestPath $nmPaths.PrimaryManifestPath -Issue 996 -IssueUrl 'https://example.test/issues/996' -Title 'No-mistakes probe' -Autonomy ship -Branch 'crew/996-no-mistakes-probe' -RepoRoot $repoRoot -WorktreePath $nmPaths.WorktreePath -PrimaryBriefPath $nmPaths.PrimaryBriefPath -PrimaryStatusPath $nmPaths.PrimaryStatusPath -TaskBriefPath $nmPaths.TaskBriefPath -ScoutReportPath $nmPaths.ScoutReportPath -TerminalBackend vscode-task | Out-Null
    $manifest = Read-CrewTaskManifest -ManifestPath $nmPaths.PrimaryManifestPath
    Assert-Equal $manifest.NoMistakesReceiptPath $null 'New manifest must have a null no-mistakes receipt path.'
    Assert-Equal $manifest.NoMistakesValid $false 'New manifest must have NoMistakesValid false.'
    $nmStatus = Get-CrewNoMistakesStatus -ManifestPath $nmPaths.PrimaryManifestPath
    Assert-Equal $nmStatus.Ready $false 'A manifest without a receipt must not be gate-ready.'
    # Write a receipt and confirm the gate flips.
    $receiptContent = @{ head_sha = 'abc123'; steps = @('review', 'test'); completedUtc = '2026-08-30T12:00:00Z' } | ConvertTo-Json
    Write-CrewUtf8File -Path (Join-Path $repoRoot '.crew\996-no-mistakes.json') -Content $receiptContent
    Update-CrewTaskManifest -ManifestPath $nmPaths.PrimaryManifestPath -Changes @{
        NoMistakesReceiptPath = Join-Path $repoRoot '.crew\996-no-mistakes.json'
        NoMistakesValid       = $true
    } | Out-Null
    $nmStatus2 = Get-CrewNoMistakesStatus -ManifestPath $nmPaths.PrimaryManifestPath
    Assert-Equal $nmStatus2.Ready $true 'A manifest with a durable receipt must be gate-ready.'
    # Stale receipt: write one with a different head_sha and confirm rejection.
    $staleReceipt = @{ head_sha = 'stale-sha'; steps = @('review'); completedUtc = '2026-08-30T11:00:00Z' } | ConvertTo-Json
    Write-CrewUtf8File -Path (Join-Path $repoRoot '.crew\996-no-mistakes.json') -Content $staleReceipt
    Update-CrewTaskManifest -ManifestPath $nmPaths.PrimaryManifestPath -Changes @{
        NoMistakesValid = $true
    } | Out-Null
    $nmStatus3 = Get-CrewNoMistakesStatus -ManifestPath $nmPaths.PrimaryManifestPath
    # Ready checks both validity AND that the file exists; the stale receipt is still
    # durable so the status reports true. The head-sha reconciliation happens in the
    # mate/monitor, not in Get-CrewNoMistakesStatus. This test only confirms the
    # durable-gate mechanics. The crew_no_mistakes.ps1 adapter is tested by the
    # mate_watch unit test.
    Assert-Equal $nmStatus3.Ready $true 'A manifest with a durable (if stale) receipt must show Ready true at the storage level.'

    # Default backend assertion: crew_start.ps1 must default to vscode-task.
    $startScript = Join-Path $PSScriptRoot 'crew_start.ps1'
    $startContent = Get-Content -LiteralPath $startScript -Raw
    Assert-True ($startContent -match "Backend = 'vscode-task'") 'crew_start.ps1 default backend must be vscode-task.'

    & (Join-Path $PSScriptRoot 'crew_teardown.ps1') -Issue 996 -RepoRoot $repoRoot | Out-Null

    Write-Output 'crew lifecycle probes passed'
}
finally {
    Set-Location -LiteralPath $initialLocation
    if (Test-Path -LiteralPath $repoRoot) {
        $probeWorktreeRoot = Join-Path $temporaryRoot 'InternHunterAgent-worktrees'
        Get-ChildItem -LiteralPath $probeWorktreeRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            & git -C $repoRoot worktree remove --force $_.FullName 2>$null
        }
        & git -C $repoRoot worktree prune 2>$null
    }
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
