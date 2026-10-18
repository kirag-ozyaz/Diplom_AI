# Full stage-4 metrics: infra -> Hit@k -> generation (live) -> performance + LLM-judge.
# Usage:
#   run_all.ps1
#   run_all.ps1 -MilvusOnlyHitk
#   run_all.ps1 -SkipPerfJudge          # без performance / LLM-judge
#   run_all.ps1 -SnapshotMilvusLogs   # после цепочки — снимок в infra/milvus/logs/

param(
    [switch]$MilvusOnlyHitk,
    [switch]$SkipPerfJudge,
    [switch]$SnapshotMilvusLogs
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $here "..\..")).Path
$logDir = Join-Path $ProjectRoot "scripts\stage4_eval\results\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:STAGE4_RUN_LOG = Join-Path $logDir ("pipeline_" + (Get-Date -Format "yyyy-MM-dd_HH-mm-ss") + ".log")

. (Join-Path $here "_root.ps1")

$flags = @()
if ($MilvusOnlyHitk) { $flags += "-MilvusOnlyHitk" }
if ($SkipPerfJudge) { $flags += "-SkipPerfJudge" }
if ($SnapshotMilvusLogs) { $flags += "-SnapshotMilvusLogs" }
$flagStr = if ($flags.Count) { $flags -join ", " } else { "(нет)" }

Write-Stage4Banner -Step "[0/5]" -Title "Полный прогон метрик этапа 4" -Detail "infra → Hit@k → generation (live) → performance → LLM-judge"
Write-Stage4Log "run_all.ps1 | флаги: $flagStr"

function Invoke-MilvusLogSnapshot {
    Write-Host "Снимок логов Milvus (start_milvus_logs.py)..."
    & $Python scripts\infra_start_system\start_milvus_logs.py
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "start_milvus_logs.py завершился с кодом $LASTEXITCODE (Docker запущен?)."
    }
}

$env:STAGE4_BANNER_STEP = "[1/5]"
Write-Stage4Log "→ run_infra.ps1"
& (Join-Path $here "run_infra.ps1")
if ($LASTEXITCODE -ne 0) {
    Invoke-MilvusLogSnapshot
    exit $LASTEXITCODE
}

$env:STAGE4_BANNER_STEP = "[2/5]"
Write-Stage4Log "→ run_hitk.ps1"
& (Join-Path $here "run_hitk.ps1")
if ($LASTEXITCODE -ne 0) {
    Invoke-MilvusLogSnapshot
    exit $LASTEXITCODE
}

if ($MilvusOnlyHitk) {
    Write-Host "Hit@k done (-MilvusOnlyHitk: generation skipped)."
    if ($SnapshotMilvusLogs) { Invoke-MilvusLogSnapshot }
    exit 0
}

$env:STAGE4_BANNER_STEP = "[3/5]"
Write-Stage4Log "→ run_generation.ps1 -Mode live"
& (Join-Path $here "run_generation.ps1") -Mode live
$genExit = $LASTEXITCODE
if ($genExit -ne 0) {
    Invoke-MilvusLogSnapshot
    exit $genExit
}

if (-not $SkipPerfJudge) {
    $env:STAGE4_BANNER_STEP = "[4/5]"
    Write-Stage4Log "→ run_perf_and_judge.ps1"
    & (Join-Path $here "run_perf_and_judge.ps1")
    $genExit = $LASTEXITCODE
}
Remove-Item Env:STAGE4_BANNER_STEP -ErrorAction SilentlyContinue

if ($genExit -ne 0 -or $SnapshotMilvusLogs) {
    Invoke-MilvusLogSnapshot
}
if ($genExit -eq 0) {
    Write-Stage4Log "run_all.ps1: завершено успешно"
} else {
    Write-Stage4Log "run_all.ps1: завершено с кодом $genExit"
}
Write-Stage4Log "Полный лог: $env:STAGE4_RUN_LOG"
exit $genExit
