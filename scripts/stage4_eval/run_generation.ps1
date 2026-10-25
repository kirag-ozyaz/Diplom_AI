# Run generation metrics (live / mock / dry-run).
# Usage:
#   run_generation.ps1
#   run_generation.ps1 -Mode live -LlmJudge
#   run_generation.ps1 -Mode live -StartId 23

param(
    [ValidateSet("live", "mock", "dry-run")]
    [string]$Mode = "live",
    [int]$StartId = 0,
    [int]$Limit = 0,
    [switch]$LlmJudge
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

Write-Stage4Banner -Title "Оценка generation" -Detail "режим $Mode, eval_rag_generation.py"
Write-Stage4Log "Команда: eval_rag_generation.py --mode $Mode"
$argsList = @("scripts\stage4_eval\generation\eval_rag_generation.py", "--mode", $Mode)
if ($StartId -gt 0) {
    $argsList += @("--start-id", $StartId)
}
if ($Limit -gt 0) {
    $argsList += @("--limit", $Limit)
}
if ($LlmJudge) {
    $argsList += "--llm-judge"
}

exit (Invoke-Stage4Python -ArgumentList $argsList)
