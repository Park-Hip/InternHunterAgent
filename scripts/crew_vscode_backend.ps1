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
