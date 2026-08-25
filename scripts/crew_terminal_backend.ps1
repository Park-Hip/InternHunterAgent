# crew_terminal_backend.ps1 - explicit Windows Terminal launch backend for crew workers.

function New-CrewWindowsTerminalLaunchPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$WorktreePath,
        [Parameter(Mandatory)][string]$SessionCommand
    )

    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($SessionCommand))
    return [pscustomobject]@{
        Backend = 'windows-terminal'
        FilePath = 'wt.exe'
        ArgumentList = @('-w', '0', 'nt', '-d', ('"{0}"' -f $WorktreePath), 'pwsh', '-NoExit', '-EncodedCommand', $encodedCommand)
    }
}

function Start-CrewWindowsTerminal {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$LaunchPlan
    )

    $terminal = Get-Command -Name $LaunchPlan.FilePath -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $terminal) {
        return [pscustomobject]@{ Launched = $false; Detail = 'wt.exe unavailable' }
    }

    try {
        Start-Process -FilePath $terminal.Source -ArgumentList $LaunchPlan.ArgumentList
        return [pscustomobject]@{ Launched = $true; Detail = 'Windows Terminal tab opened' }
    }
    catch {
        return [pscustomobject]@{ Launched = $false; Detail = $_.Exception.Message }
    }
}
