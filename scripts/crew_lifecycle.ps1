# crew_lifecycle.ps1 - shared, durable crew task lifecycle helpers.

function Get-CrewWorktreeRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepoRoot)

    $repo = (Resolve-Path -LiteralPath $RepoRoot).Path
    $parent = Split-Path -Parent $repo
    $name = Split-Path -Leaf $repo
    return Join-Path $parent "$name-worktrees"
}

function Get-CrewTaskPaths {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][int]$Issue
    )

    $repo = (Resolve-Path -LiteralPath $RepoRoot).Path
    $worktreeRoot = Get-CrewWorktreeRoot -RepoRoot $repo
    $worktreePath = Join-Path $worktreeRoot "IHA-$Issue"
    $crewPath = Join-Path $repo '.crew'
    $reportPath = Join-Path $repo "research\crew\$Issue-report.md"

    return [pscustomobject]@{
        WorktreeRoot       = $worktreeRoot
        WorktreePath       = $worktreePath
        PrimaryBriefPath   = Join-Path $crewPath "$Issue-brief.md"
        PrimaryStatusPath  = Join-Path $crewPath "$Issue-status.md"
        PrimaryManifestPath = Join-Path $crewPath "$Issue-task.json"
        TaskBriefPath      = Join-Path $worktreePath ".crew\$Issue-brief.md"
        TaskManifestPath   = Join-Path $worktreePath ".crew\$Issue-task.json"
        ScoutReportPath    = $reportPath
    }
}

function Resolve-CrewHarnessArgs {
    # Centralize defaults so every launch backend receives the same resolved
    # arguments. A registered Pi worker deliberately uses ModelScope, not a
    # similarly named DashScope/OpenRouter route, unless the caller supplied
    # an explicit --model override.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Harness,
        [AllowEmptyString()][string]$HarnessArgs,
        [Parameter(Mandatory)][ValidateSet('wt', 'vscode', 'vscode-task')][string]$Backend,
        [ValidateNotNullOrEmpty()][string]$PiModel = 'modelscope/deepseek-ai/DeepSeek-V4-Pro-0813'
    )

    $resolved = if ([string]::IsNullOrWhiteSpace($HarnessArgs)) {
        if ($Harness -ieq 'codex') { '--yolo' } else { '' }
    }
    else { $HarnessArgs.Trim() }

    $hasExplicitModel = $resolved -match '(?i)(?:^|\s)--model(?:\s|=)'
    if ($Harness -ieq 'pi' -and $Backend -eq 'vscode-task' -and -not $hasExplicitModel) {
        $resolved = if ($resolved) { "--model $PiModel $resolved" } else { "--model $PiModel" }
    }
    return $resolved
}

function Write-CrewUtf8File {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Content
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Write-CrewTaskManifest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ManifestPath,
        [Parameter(Mandatory)][int]$Issue,
        [Parameter(Mandatory)][string]$IssueUrl,
        [Parameter(Mandatory)][string]$Title,
        [Parameter(Mandatory)][ValidateSet('ship', 'scout')][string]$Autonomy,
        [Parameter(Mandatory)][string]$Branch,
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$WorktreePath,
        [Parameter(Mandatory)][string]$PrimaryBriefPath,
        [Parameter(Mandatory)][string]$PrimaryStatusPath,
        [Parameter(Mandatory)][string]$TaskBriefPath,
        [Parameter(Mandatory)][string]$ScoutReportPath,
            [Parameter(Mandatory)][ValidateSet('wt', 'vscode', 'vscode-task')][string]$TerminalBackend
    )

    $manifest = [ordered]@{
        SchemaVersion          = 1
        Issue                  = $Issue
        IssueUrl               = $IssueUrl
        Title                  = $Title
        Autonomy               = $Autonomy
        Branch                 = $Branch
        RepoRoot               = $RepoRoot
        WorktreePath           = $WorktreePath
        PrimaryBriefPath       = $PrimaryBriefPath
        PrimaryStatusPath      = $PrimaryStatusPath
        TaskBriefPath          = $TaskBriefPath
        ScoutReportPath        = if ($Autonomy -eq 'scout') { $ScoutReportPath } else { $null }
        ScoutReportHandedOff   = $false
        State                  = 'dispatched'
        DispatchedAtUtc        = '{0:u}' -f (Get-Date).ToUniversalTime()
        TerminalBackend        = $TerminalBackend
        TerminalLaunchStatus   = 'not-attempted'
        TornDownAtUtc          = $null
    }
    Write-CrewUtf8File -Path $ManifestPath -Content ($manifest | ConvertTo-Json -Depth 4)
    return $manifest
}

function Read-CrewTaskManifest {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        throw "Crew task manifest not found: $ManifestPath"
    }
    return Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
}

function Update-CrewTaskManifest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ManifestPath,
        [Parameter(Mandatory)][hashtable]$Changes
    )

    $manifest = Read-CrewTaskManifest -ManifestPath $ManifestPath
    foreach ($key in $Changes.Keys) {
        $manifest | Add-Member -MemberType NoteProperty -Name $key -Value $Changes[$key] -Force
    }
    Write-CrewUtf8File -Path $ManifestPath -Content ($manifest | ConvertTo-Json -Depth 4)
    return $manifest
}

function Copy-CrewTaskContractFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$PrimaryBriefPath,
        [Parameter(Mandatory)][string]$TaskBriefPath,
        [Parameter(Mandatory)][string]$PrimaryManifestPath,
        [Parameter(Mandatory)][string]$TaskManifestPath
    )

    Write-CrewUtf8File -Path $TaskBriefPath -Content (Get-Content -LiteralPath $PrimaryBriefPath -Raw)
    Write-CrewUtf8File -Path $TaskManifestPath -Content (Get-Content -LiteralPath $PrimaryManifestPath -Raw)
}

function Assert-CrewTeardownAllowed {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Manifest,
        [switch]$ConfirmScoutReportHandoff
    )

    if ($Manifest.Autonomy -ne 'scout') { return }
    if (-not $Manifest.ScoutReportPath -or -not (Test-Path -LiteralPath $Manifest.ScoutReportPath)) {
        throw "Scout report is missing at '$($Manifest.ScoutReportPath)'. Teardown is refused."
    }
    if (-not $Manifest.ScoutReportHandedOff -and -not $ConfirmScoutReportHandoff) {
        throw 'Scout report handoff has not been confirmed. Re-run with -ConfirmScoutReportHandoff after verifying the durable report.'
    }
}
