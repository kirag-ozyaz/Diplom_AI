# Full stage-4 metrics: infra -> Hit@k -> generation (live).
# Usage:
#   run_all.ps1
#   run_all.ps1 -MilvusOnlyHitk
#   run_all.ps1 -SnapshotMilvusLogs   # после цепочки — снимок в infra/milvus/logs/

param(
    [switch]$MilvusOnlyHitk,
    [switch]$SnapshotMilvusLogs
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
. (Join-Path $here "_root.ps1")

function Invoke-MilvusLogSnapshot {
    Write-Host "Снимок логов Milvus (start_milvus_logs.py)..."
    & $Python scripts\start_milvus_logs.py
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "start_milvus_logs.py завершился с кодом $LASTEXITCODE (Docker запущен?)."
    }
}

& (Join-Path $here "run_infra.ps1")
if ($LASTEXITCODE -ne 0) {
    Invoke-MilvusLogSnapshot
    exit $LASTEXITCODE
}

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

& (Join-Path $here "run_generation.ps1") -Mode live
$genExit = $LASTEXITCODE
if ($genExit -ne 0 -or $SnapshotMilvusLogs) {
    Invoke-MilvusLogSnapshot
}
exit $genExit
