# crew_vscode_backend.ps1 - VS Code launch backends for crew workers.

function Add-CrewVsCodeTaskEntry {
    # Registers (or replaces) a "Crew: IHA-<issue> worker" task in the primary
    # checkout's .vscode/tasks.json so the maintainer can start the worker from
    # the integrated terminal panel of an already-running VS Code window
    # (Terminal > Run Task). The CLI cannot inject terminals into running windows,
    # so a workspace task is the only way to land a worker inside them.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$WorktreePath,
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][string]$HarnessPath,
        [AllowEmptyString()][string]$HarnessArgs,
        [Parameter(Mandatory)][string]$WorkerPrompt
    )

    $tasksDir = Join-Path $RepoRoot '.vscode'
    $tasksPath = Join-Path $tasksDir 'tasks.json'

    if (Test-Path -LiteralPath $tasksPath) {
        try {
            $config = Get-Content -LiteralPath $tasksPath -Raw | ConvertFrom-Json
        }
        catch {
            throw ".vscode/tasks.json exists but is not valid JSON: $($_.Exception.Message)"
        }
    }
    else {
        $config = [pscustomobject]@{
            version = '2.0.0'
            tasks   = @()
        }
    }

    if (-not ($config | Get-Member -Name tasks)) {
        $config | Add-Member -MemberType NoteProperty -Name tasks -Value @()
    }
    $tasks = @($config.tasks | Where-Object { $_.label -ne $TaskName })

    $args = @()
    foreach ($arg in ($HarnessArgs -split '\s+' | Where-Object { $_ })) { $args += $arg }
    $args += $WorkerPrompt

    $entry = [ordered]@{
        label          = $TaskName
        type           = 'shell'
        isBackground   = $true
        problemMatcher = @()
        presentation   = [ordered]@{ reveal = 'always'; focus = $true; panel = 'dedicated'; clear = $true }
        options        = [ordered]@{ cwd = $WorktreePath }
        command        = $HarnessPath
        args           = $args
    }
    $tasks += [pscustomobject]$entry

    if (-not ($config | Get-Member -Name version)) {
        $config | Add-Member -MemberType NoteProperty -Name version -Value '2.0.0' -Force
    }
    $config.tasks = $tasks

    if (-not (Test-Path -LiteralPath $tasksDir)) {
        New-Item -ItemType Directory -Path $tasksDir -Force | Out-Null
    }
    $json = $config | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($tasksPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    return $tasksPath
}

function Remove-CrewVsCodeTaskEntry {
    # Mirror image of Add-CrewVsCodeTaskEntry: removes every task entry whose
    # options.cwd matches the torn-down worktree path from the primary
    # checkout's .vscode/tasks.json so retired workers do not leave stale
    # Run Task entries behind. Matching keys off cwd rather than label so the
    # removal stays robust even if the label suffix or harness differs.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$WorktreePath
    )

    $tasksPath = Join-Path (Join-Path $RepoRoot '.vscode') 'tasks.json'
    if (-not (Test-Path -LiteralPath $tasksPath)) {
        return [pscustomobject]@{ Removed = 0; TasksPath = $tasksPath }
    }
    try {
        $config = Get-Content -LiteralPath $tasksPath -Raw | ConvertFrom-Json
    }
    catch {
        throw ".vscode/tasks.json exists but is not valid JSON: $($_.Exception.Message)"
    }
    if (-not ($config | Get-Member -Name tasks)) {
        return [pscustomobject]@{ Removed = 0; TasksPath = $tasksPath }
    }

    $remaining = @($config.tasks | Where-Object { $_.options.cwd -ne $WorktreePath })
    $removed = @($config.tasks).Count - $remaining.Count
    if ($removed -gt 0) {
        $config.tasks = $remaining
        $json = $config | ConvertTo-Json -Depth 6
        [System.IO.File]::WriteAllText($tasksPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    }
    return [pscustomobject]@{ Removed = $removed; TasksPath = $tasksPath }
}
#
# The VS Code CLI cannot inject an integrated-terminal session into an
# already-running window. This backend therefore opens the task worktree in a
# NEW VS Code window and pre-writes a .vscode/tasks.json terminal task so the
# harness starts in the integrated terminal panel when the folder opens
# (requires automatic tasks to be allowed: "task.allowAutomaticTasks": "on").

function New-CrewVsCodeLaunchPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$WorktreePath,
        [Parameter(Mandatory)][string]$SessionCommand,
        [Parameter(Mandatory)][string]$TaskName
    )

    $vscode = Get-Command -Name 'code' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $vscode) {
        return $null
    }

    return [pscustomobject]@{
        Backend       = 'vscode'
        FilePath      = $vscode.Source
        ArgumentList  = @('-n', $WorktreePath)
        WorktreePath  = $WorktreePath
        SessionCommand = $SessionCommand
        TaskName      = $TaskName
    }
}

function Write-CrewVsCodeTerminalTask {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$WorktreePath,
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][string]$SessionCommand
    )

    $tasks = [ordered]@{
        version = '2.0.0'
        tasks   = @(
            [ordered]@{
                label          = $TaskName
                type           = 'shell'
                command        = $SessionCommand
                isBackground   = $true
                presentation   = [ordered]@{
                    reveal   = 'always'
                    focus    = $true
                    panel    = 'dedicated'
                    clear    = $true
                }
                runOptions     = [ordered]@{
                    runOn = 'folderOpen'
                }
                problemMatcher = @()
            }
        )
    }
    $json = $tasks | ConvertTo-Json -Depth 6
    $dir = Join-Path $WorktreePath '.vscode'
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText((Join-Path $dir 'tasks.json'), $json, [System.Text.UTF8Encoding]::new($false))
}

function Start-CrewVsCode {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$LaunchPlan
    )

    try {
        Start-Process -FilePath $LaunchPlan.FilePath -ArgumentList ($LaunchPlan.ArgumentList | ForEach-Object { '"{0}"' -f $_ })
        return [pscustomobject]@{ Launched = $true; Detail = 'VS Code window opened' }
    }
    catch {
        return [pscustomobject]@{ Launched = $false; Detail = $_.Exception.Message }
    }
}

#
# vscode-task-auto backend: publish an immutable launch request that a local
# VS Code extension picks up and runs in the already-open primary window. The
# launcher builds one canonical execution spec (type/command/args/cwd) and its
# SHA-256 hash, stores both in the task manifest and the request, then polls the
# append-only result log for the first terminal launch event.

function New-CrewExecutionSpec {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$HarnessPath,
        [AllowEmptyString()][string]$HarnessArgs,
        [Parameter(Mandatory)][string]$WorkerPrompt,
        [Parameter(Mandatory)][string]$WorktreePath
    )

    # Mirrors Add-CrewVsCodeTaskEntry's argument construction so the canonical
    # spec and the registered task entry byte-for-byte describe the same run.
    $argList = @()
    foreach ($arg in ($HarnessArgs -split '\s+' | Where-Object { $_ })) { $argList += $arg }
    $argList += $WorkerPrompt
    return [ordered]@{
        specVersion = 1
        type        = 'shell'
        command     = $HarnessPath
        args        = [string[]]$argList
        cwd         = $WorktreePath
    }
}

function Get-CrewExecutionSpecHash {
    # Byte-identical to vscode/crew-launcher/lib/spec.js canonicalString +
    # specHash: one LF-joined string of the same ordered fields, UTF-8, SHA-256
    # hex. A regression test in test_crew_lifecycle.ps1 pins a shared vector.
    [CmdletBinding()]
    param([Parameter(Mandatory)][System.Collections.IDictionary]$Spec)

    $lines = @(
        "specVersion=$($Spec['specVersion'])",
        "type=$($Spec['type'])",
        "command=$($Spec['command'])",
        "args=$($Spec['args'].Count)"
    )
    foreach ($arg in $Spec['args']) { $lines += [string]$arg }
    $lines += "cwd=$($Spec['cwd'])"
    $canonical = $lines -join "`n"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($canonical)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Add-CrewVsCodeAutoRequest {
    # Publishes one immutable request record and atomically moves it into place. The request never carries a free-form shell command - only
    # the pinned spec and its hash.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$RequestId,
        [Parameter(Mandatory)][int]$Issue,
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][string]$WorktreePath,
        [Parameter(Mandatory)][System.Collections.IDictionary]$ExecutionSpec,
        [Parameter(Mandatory)][string]$ManifestPath
    )

    $specHash = Get-CrewExecutionSpecHash -Spec $ExecutionSpec
    $requestsDir = Join-Path (Join-Path (Join-Path $RepoRoot '.crew') 'launch-queue') 'requests'
    if (-not (Test-Path -LiteralPath $requestsDir)) {
        New-Item -ItemType Directory -Path $requestsDir -Force | Out-Null
    }
    $request = [ordered]@{
        schemaVersion     = 1
        requestId         = $RequestId
        issue             = $Issue
        taskName          = $TaskName
        worktreePath      = $WorktreePath
        executionSpec     = $ExecutionSpec
        executionSpecHash = $specHash
        manifestPath      = $ManifestPath
        createdUtc        = '{0:u}' -f (Get-Date).ToUniversalTime()
    }
    $json = $request | ConvertTo-Json -Depth 6
    $finalPath = Join-Path $requestsDir ($RequestId + '.json')
    $tempPath = Join-Path $requestsDir ('.tmp-' + [guid]::NewGuid().ToString('N'))
    [System.IO.File]::WriteAllText($tempPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    try {
        [System.IO.File]::Move($tempPath, $finalPath)
    }
    catch {
        if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue }
        throw
    }
    return $finalPath
}

function Get-CrewVsCodeAutoLaunchEvent {
    # Returns the first terminal launch event kind written by the extension, or
    # $null when the extension has not (yet) produced one.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$RequestId
    )

    $resultsDir = Join-Path (Join-Path (Join-Path $RepoRoot '.crew') 'launch-queue') 'results'
    $eventsPath = Join-Path $resultsDir ($RequestId + '.events.jsonl')
    if (-not (Test-Path -LiteralPath $eventsPath)) { return $null }
    foreach ($line in Get-Content -LiteralPath $eventsPath) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $event = $line | ConvertFrom-Json } catch { continue }
        if ($event.event -in @('accepted', 'started', 'already-running', 'refused', 'failed')) {
            return $event.event
        }
    }
    return $null
}

function Wait-CrewVsCodeAutoLaunch {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$RequestId,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $event = Get-CrewVsCodeAutoLaunchEvent -RepoRoot $RepoRoot -RequestId $RequestId
        if ($event) { return $event }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    return $null
}

function Remove-CrewVsCodeAutoRecords {
    # Removes only the request and result records owned by one request id.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$RequestId
    )

    $launchQueue = Join-Path (Join-Path $RepoRoot '.crew') 'launch-queue'
    $requestPath = Join-Path (Join-Path $launchQueue 'requests') ($RequestId + '.json')
    $resultsPath = Join-Path (Join-Path $launchQueue 'results') ($RequestId + '.events.jsonl')
    $removed = 0
    if (Test-Path -LiteralPath $requestPath) { Remove-Item -LiteralPath $requestPath -Force; $removed++ }
    if (Test-Path -LiteralPath $resultsPath) { Remove-Item -LiteralPath $resultsPath -Force; $removed++ }
    return [pscustomobject]@{ Removed = $removed }
}

function Get-CrewVsCodeAutoLaunchStatus {
    # Maps an extension launch event (or $null from the poll window) to the
    # manifest status/detail the launcher records.
    [CmdletBinding()]
    param([AllowNull()][string]$LaunchEvent)

    switch ($LaunchEvent) {
        'accepted'        { return [pscustomobject]@{ Status = 'launched'; Detail = 'extension accepted the task for execution' } }
        'started'         { return [pscustomobject]@{ Status = 'launched'; Detail = 'worker process started in the current window' } }
        'already-running' { return [pscustomobject]@{ Status = 'already-running'; Detail = 'a matching worker is already running' } }
        'refused'         { return [pscustomobject]@{ Status = 'refused'; Detail = 'extension refused the request; see the request event log' } }
        'failed'          { return [pscustomobject]@{ Status = 'failed'; Detail = 'extension failed to start the task' } }
        default           { return [pscustomobject]@{ Status = 'pending-extension'; Detail = 'no extension result within the poll window (extension missing or disabled)' } }
    }
}
