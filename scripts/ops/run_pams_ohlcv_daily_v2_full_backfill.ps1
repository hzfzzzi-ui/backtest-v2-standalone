param(
    [string]$Start = "2007-01-04",
    [string]$End = "2026-03-16",
    [string]$RunName = "",
    [string]$SymbolsCsv = "",
    [string]$ResumeFromStep = "",
    [string]$ResumeTradeDate = "",
    [switch]$Apply,
    [switch]$KeepContainer
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

function Write-TextAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $dir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $tmpPath = "$Path.tmp"
    Set-Content -Path $tmpPath -Value $Content -Encoding UTF8
    Move-Item -Path $tmpPath -Destination $Path -Force
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\\.."))
$composeFile = Join-Path $repoRoot "docker-compose.yml"
$outputsRoot = Join-Path $repoRoot "outputs\\ops"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = "pams_ohlcv_daily_v2_full_backfill_$stamp"
}
$outputDir = Join-Path $outputsRoot $RunName
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$statusPath = Join-Path $outputDir "launcher_status.json"
$exitCodePath = Join-Path $outputDir "exit_code.txt"
$containerStatePath = Join-Path $outputDir "worker_container_state.json"
$containerNamePath = Join-Path $outputDir "worker_container_name.txt"
$containerLogPath = Join-Path $outputDir "worker_container.log"
$runNameInContainer = "/app/outputs/ops/$RunName"
$containerName = "backtest-v2-full-backfill-$stamp"

$startedAt = (Get-Date).ToString("s")
Write-TextAtomic -Path $containerNamePath -Content $containerName
Write-JsonAtomic -Path $statusPath -Payload @{
    status = "launching"
    started_at = $startedAt
    updated_at = $startedAt
    run_name = $RunName
    output_dir = $outputDir
    container_name = $containerName
    date_range = @{
        start = $Start
        end = $End
    }
    resume_from_step = $ResumeFromStep
    resume_trade_date = $ResumeTradeDate
    apply = [bool]$Apply
    symbols_csv = $SymbolsCsv
}

$dockerArgs = @(
    "compose", "--profile", "worker", "-f", $composeFile,
    "run", "-d",
    "--name", $containerName,
    "backtest-v2-worker",
    "python", "-m", "backend.cli",
    "data_refresh", "--target", "pams_ohlcv_daily_v2_full_backfill", "--",
    "--start", $Start,
    "--end", $End,
    "--output-dir", $runNameInContainer
)
if (-not [string]::IsNullOrWhiteSpace($SymbolsCsv)) {
    $dockerArgs += @("--symbols-csv", $SymbolsCsv)
}
if (-not [string]::IsNullOrWhiteSpace($ResumeFromStep)) {
    $dockerArgs += @("--resume-from-step", $ResumeFromStep)
}
if (-not [string]::IsNullOrWhiteSpace($ResumeTradeDate)) {
    $dockerArgs += @("--resume-trade-date", $ResumeTradeDate)
}
if ($Apply) {
    $dockerArgs += "--apply"
}

$containerId = ""
$waitExitCode = ""

try {
    & docker @dockerArgs | Out-Null
    $containerId = (& docker inspect $containerName --format "{{.Id}}" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerId)) {
        throw "failed to start worker container"
    }

    Write-JsonAtomic -Path $statusPath -Payload @{
        status = "running"
        started_at = $startedAt
        updated_at = (Get-Date).ToString("s")
        run_name = $RunName
        output_dir = $outputDir
        container_name = $containerName
        container_id = $containerId
        date_range = @{
            start = $Start
            end = $End
        }
        resume_from_step = $ResumeFromStep
        resume_trade_date = $ResumeTradeDate
        apply = [bool]$Apply
        symbols_csv = $SymbolsCsv
    }

    $waitExitCode = (& docker wait $containerName).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "docker wait failed"
    }
}
catch {
    Write-TextAtomic -Path $exitCodePath -Content "1"
    Write-JsonAtomic -Path $statusPath -Payload @{
        status = "launcher_failed"
        started_at = $startedAt
        finished_at = (Get-Date).ToString("s")
        updated_at = (Get-Date).ToString("s")
        run_name = $RunName
        output_dir = $outputDir
        container_name = $containerName
        container_id = $containerId
        error = @{
            message = $_.Exception.Message
        }
    }
    throw
}
finally {
    $stateJson = ""
    try {
        $stateJson = & docker inspect $containerName --format "{{json .State}}"
    }
    catch {
        $stateJson = ""
    }
    $state = $null
    if (-not [string]::IsNullOrWhiteSpace($stateJson)) {
        $state = $stateJson | ConvertFrom-Json
        Write-JsonAtomic -Path $containerStatePath -Payload $state
    }
    try {
        $logs = & docker logs $containerName 2>&1
        $logs | Set-Content -Path $containerLogPath -Encoding UTF8
    }
    catch {
    }

    if (-not [string]::IsNullOrWhiteSpace($waitExitCode)) {
        Write-TextAtomic -Path $exitCodePath -Content $waitExitCode
        $finalStatus = if ($state -and $state.OOMKilled) { "failed_oom" } elseif ([int]$waitExitCode -eq 0) { "completed" } else { "failed" }
        Write-JsonAtomic -Path $statusPath -Payload @{
            status = $finalStatus
            started_at = $startedAt
            finished_at = (Get-Date).ToString("s")
            updated_at = (Get-Date).ToString("s")
            run_name = $RunName
            output_dir = $outputDir
            container_name = $containerName
            container_id = $containerId
            container_state = $state
        }
    }

    if (-not $KeepContainer) {
        try {
            & docker rm -f $containerName | Out-Null
        }
        catch {
        }
    }
}
