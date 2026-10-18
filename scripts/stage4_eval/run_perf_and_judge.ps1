# PowerShell: performance + LLM judge (Russian banners printed by Python).
# Usage: run_perf_and_judge.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

if (-not $env:STAGE4_BANNER_STEP) {
    $env:STAGE4_BANNER_STEP = "[1/2]"
}
Write-Stage4Log "Команда: eval_rag_performance.py"
& $Python scripts\stage4_eval\generation\eval_rag_performance.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($env:STAGE4_BANNER_STEP -eq "[4/5]") {
    $env:STAGE4_BANNER_STEP = "[5/5]"
} else {
    $env:STAGE4_BANNER_STEP = "[2/2]"
}
Write-Stage4Log "Команда: eval_rag_llm_judge.py"
& $Python scripts\stage4_eval\generation\eval_rag_llm_judge.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts\stage4_eval\lib\print_run_done.py
