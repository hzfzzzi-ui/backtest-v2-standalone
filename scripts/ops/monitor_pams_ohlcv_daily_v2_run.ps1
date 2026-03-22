param(
    [Parameter(Mandatory = $true)][string]$RunDir,
    [int]$IntervalSeconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Payload
    )
    $dir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $tmpPath = "$Path.tmp"
    $Payload | ConvertTo-Json -Depth 12 | Set-Content -Path $tmpPath -Encoding UTF8
    Move-Item -Path $tmpPath -Destination $Path -Force
}

function Read-JsonOrNull {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    $text = Get-Content -Path $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }
    return $text | ConvertFrom-Json
}

function Read-TextOrEmpty {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) {
        return ""
    }
    return (Get-Content -Path $Path -Raw -Encoding UTF8).Trim()
}

function Get-ObjectPropertyOrNull {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $Object) {
        return $null
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) {
        return $null
    }
    return $prop.Value
}

function Get-ContainerStateSnapshot {
    param([string]$ContainerName)
    if ([string]::IsNullOrWhiteSpace($ContainerName)) {
        return $null
    }
    try {
        $json = & docker inspect $ContainerName --format "{{json .State}}" 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) {
            return [ordered]@{
                container_name = $ContainerName
                found = $false
            }
        }
        $state = $json | ConvertFrom-Json
        return [ordered]@{
            container_name = $ContainerName
            found = $true
            status = $state.Status
            running = [bool]$state.Running
            oom_killed = [bool]$state.OOMKilled
            exit_code = $state.ExitCode
            started_at = $state.StartedAt
            finished_at = $state.FinishedAt
        }
    }
    catch {
        return [ordered]@{
            container_name = $ContainerName
            found = $false
            inspect_error = $_.Exception.Message
        }
    }
}

$runDirFull = [System.IO.Path]::GetFullPath($RunDir)
if (-not (Test-Path $runDirFull)) {
    throw "run dir not found: $runDirFull"
}

$statusPath = Join-Path $runDirFull "status.json"
$heartbeatPath = Join-Path $runDirFull "heartbeat.json"
$launcherStatusPath = Join-Path $runDirFull "launcher_status.json"
$currentStepPath = Join-Path $runDirFull "current_step.txt"
$exitCodePath = Join-Path $runDirFull "exit_code.txt"
$containerNamePath = Join-Path $runDirFull "worker_container_name.txt"
$monitorLogPath = Join-Path $runDirFull "monitor_log.jsonl"
$monitorStatusPath = Join-Path $runDirFull "monitor_status.json"
$stopFlagPath = Join-Path $runDirFull "stop_monitor.txt"

while ($true) {
    $status = Read-JsonOrNull -Path $statusPath
    $heartbeat = Read-JsonOrNull -Path $heartbeatPath
    $launcher = Read-JsonOrNull -Path $launcherStatusPath
    $containerName = Read-TextOrEmpty -Path $containerNamePath
    $exitCode = Read-TextOrEmpty -Path $exitCodePath
    $containerState = Get-ContainerStateSnapshot -ContainerName $containerName

    $snapshot = [ordered]@{
        captured_at = (Get-Date).ToString("s")
        run_dir = $runDirFull
        current_step = Read-TextOrEmpty -Path $currentStepPath
        status = Get-ObjectPropertyOrNull -Object $status -Name "status"
        status_current_step = Get-ObjectPropertyOrNull -Object $status -Name "current_step"
        heartbeat_step = Get-ObjectPropertyOrNull -Object $heartbeat -Name "step"
        heartbeat_status = Get-ObjectPropertyOrNull -Object $heartbeat -Name "status"
        heartbeat_updated_at = Get-ObjectPropertyOrNull -Object $heartbeat -Name "updated_at"
        heartbeat_trade_date = Get-ObjectPropertyOrNull -Object $heartbeat -Name "trade_date"
        heartbeat_run_id = Get-ObjectPropertyOrNull -Object $heartbeat -Name "run_id"
        heartbeat_build_run_id = Get-ObjectPropertyOrNull -Object $heartbeat -Name "build_run_id"
        launcher_status = Get-ObjectPropertyOrNull -Object $launcher -Name "status"
        exit_code_present = (Test-Path $exitCodePath)
        exit_code = if ([string]::IsNullOrWhiteSpace($exitCode)) { $null } else { $exitCode }
        container = $containerState
    }

    $snapshot | ConvertTo-Json -Compress -Depth 12 | Add-Content -Path $monitorLogPath -Encoding UTF8
    Write-JsonAtomic -Path $monitorStatusPath -Payload $snapshot

    $terminalStatus = if ($null -eq $status) { "" } else { [string]$status.status }
    if ((Test-Path $stopFlagPath) -or (Test-Path $exitCodePath) -or $terminalStatus -in @("completed", "failed", "dry_run")) {
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
}
