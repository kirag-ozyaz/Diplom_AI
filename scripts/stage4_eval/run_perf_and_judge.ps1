# PowerShell: performance + LLM judge (Russian banners printed by Python).
# Usage: run_perf_and_judge.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

& $Python scripts\stage4_eval\generation\eval_rag_performance.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts\stage4_eval\generation\eval_rag_llm_judge.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts\stage4_eval\lib\print_run_done.py
