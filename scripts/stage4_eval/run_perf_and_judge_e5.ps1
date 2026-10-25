# PowerShell: performance + LLM judge opyt 1 (E5 JSON).
# Usage: run_perf_and_judge_e5.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

$perfOut = "scripts\stage4_eval\results\generation\stage4_performance_metrics_e5.json"
$judgeOut = "scripts\stage4_eval\results\generation\stage4_llm_judge_metrics_e5.json"
$config = "src\preprocessing\Create_embeddings\E5\rag_runtime_e5.json"

if (-not $env:STAGE4_BANNER_STEP) {
    $env:STAGE4_BANNER_STEP = "[1/2]"
}
Write-Stage4Banner -Title "Оценка производительности (опыт 1, E5)" -Detail "eval_rag_performance.py, JSON stage4_performance_metrics_e5.json"
Write-Stage4Log "Команда: eval_rag_performance.py (e5)"
$exitCode = Invoke-Stage4Python -ArgumentList @(
    "scripts\stage4_eval\generation\eval_rag_performance.py",
    "--config", $config,
    "--out", $perfOut
)
if ($exitCode -ne 0) { exit $exitCode }

if ($env:STAGE4_BANNER_STEP -eq "[4/5]") {
    $env:STAGE4_BANNER_STEP = "[5/5]"
} else {
    $env:STAGE4_BANNER_STEP = "[2/2]"
}
Write-Stage4Banner -Title "Оценка качества LLM-as-a-Judge (опыт 1, E5)" -Detail "eval_rag_llm_judge.py, JSON stage4_llm_judge_metrics_e5.json"
Write-Stage4Log "Команда: eval_rag_llm_judge.py (e5)"
$exitCode = Invoke-Stage4Python -ArgumentList @(
    "scripts\stage4_eval\generation\eval_rag_llm_judge.py",
    "--config", $config,
    "--out", $judgeOut
)
if ($exitCode -ne 0) { exit $exitCode }

Invoke-Stage4Python -ArgumentList @("scripts\stage4_eval\lib\print_run_done.py") | Out-Null
exit 0
