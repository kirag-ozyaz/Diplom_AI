# Run generation metrics opyt 1 (E5): live / mock / dry-run.
# Usage:
#   run_generation_e5.ps1
#   run_generation_e5.ps1 -Mode live
#   run_generation_e5.ps1 -Mode live -StartId 23

param(
    [ValidateSet("live", "mock", "dry-run")]
    [string]$Mode = "live",
    [int]$StartId = 0,
    [int]$Limit = 0,
    [switch]$LlmJudge
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

$genDetail = "режим $Mode, коллекция diplom_multimodal_e5, stage4_gen_eval_results_e5.json"
if ($Mode -eq "live") {
    $genDetail += "; eval_rag_generation.py (e5)"
}
Write-Stage4Banner -Title "Оценка generation (опыт 1, E5)" -Detail $genDetail
Write-Stage4Log "Команда: eval_rag_generation.py --mode $Mode (e5)"
$argsList = @(
    "scripts\stage4_eval\generation\eval_rag_generation.py",
    "--mode", $Mode,
    "--out", "scripts\stage4_eval\results\generation\stage4_gen_eval_results_e5.json",
    "--hitk", "scripts\stage4_eval\results\retrieval\stage4_hitk_results_e5.json",
    "--config", "src\preprocessing\Create_embeddings\E5\rag_runtime_e5.json",
    "--e5-query-prefix"
)
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
