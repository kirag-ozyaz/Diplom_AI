# MRR/nDCG for three retrieval experiments (base, e5, rerank) plus comparison table.
# Usage:
#   run_rank_all.ps1
#   run_rank_all.ps1 -SkipInfra
#   run_rank_all.ps1 -LimitQuestions 5

param(
    [switch]$SkipInfra,
    [int]$LimitQuestions = 0
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $here "..\..")).Path
$logDir = Join-Path $ProjectRoot "scripts\stage4_eval\results\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:STAGE4_RUN_LOG = Join-Path $logDir ("pipeline_" + (Get-Date -Format "yyyy-MM-dd_HH-mm-ss") + "_rank.log")

. (Join-Path $here "_root.ps1")

Write-Stage4Banner -Step "[0/4]" -Title "MRR / nDCG@k three retrieval runs" -Detail "base -> e5 -> rerank -> rank_metrics"
Write-Stage4Log "run_rank_all.ps1"

if (-not $SkipInfra) {
    $env:STAGE4_BANNER_STEP = "[1/4]"
    Write-Stage4Log "-> run_infra.ps1"
    & (Join-Path $here "run_infra.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$step = if ($SkipInfra) { 1 } else { 2 }
foreach ($mode in @("base", "e5", "rerank")) {
    $env:STAGE4_BANNER_STEP = "[$step/4]"
    Write-Stage4Log "-> run_rank.ps1 -Mode $mode"
    if ($LimitQuestions -gt 0) {
        & (Join-Path $here "run_rank.ps1") -Mode $mode -LimitQuestions $LimitQuestions
    } else {
        & (Join-Path $here "run_rank.ps1") -Mode $mode
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $step++
}

$env:STAGE4_BANNER_STEP = "[4/4]"
Write-Stage4Log "-> run_rank_metrics.ps1"
& (Join-Path $here "run_rank_metrics.ps1")
$exitCode = $LASTEXITCODE
Remove-Item Env:STAGE4_BANNER_STEP -ErrorAction SilentlyContinue
Write-Stage4Log ("run_rank_all.ps1: exit " + $exitCode + " | log: " + $env:STAGE4_RUN_LOG)
exit $exitCode
