# crew_vscode_backend.ps1 - explicit VS Code launch backend for crew workers.
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
