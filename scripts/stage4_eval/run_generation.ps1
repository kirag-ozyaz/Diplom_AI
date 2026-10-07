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

$argsList = @("scripts\stage4_eval\eval_rag_generation.py", "--mode", $Mode)
if ($StartId -gt 0) {
    $argsList += @("--start-id", $StartId)
}
if ($Limit -gt 0) {
    $argsList += @("--limit", $Limit)
}
if ($LlmJudge) {
    $argsList += "--llm-judge"
}

& $Python @argsList
exit $LASTEXITCODE
