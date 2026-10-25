# Run generation metrics opyt 2 (rerank): live / mock / dry-run.
# Usage:
#   run_generation_rerank.ps1
#   run_generation_rerank.ps1 -Mode live
#   run_generation_rerank.ps1 -Mode live -StartId 23

param(
    [ValidateSet("live", "mock", "dry-run")]
    [string]$Mode = "live",
    [int]$StartId = 0,
    [int]$Limit = 0,
    [switch]$LlmJudge
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

$genDetail = "режим $Mode, коллекция diplom_multimodal_e5_rerank, stage4_gen_eval_results_rerank.json"
if ($Mode -eq "live") {
    $genDetail += "; eval_rag_generation.py (rerank)"
}
Write-Stage4Banner -Title "Оценка generation (опыт 2, реранкер)" -Detail $genDetail
Write-Stage4Log "Команда: eval_rag_generation.py --mode $Mode (rerank)"
$argsList = @(
    "scripts\stage4_eval\generation\eval_rag_generation.py",
    "--mode", $Mode,
    "--out", "scripts\stage4_eval\results\generation\stage4_gen_eval_results_rerank.json",
    "--hitk", "scripts\stage4_eval\results\retrieval\stage4_hitk_results_rerank.json",
    "--config", "src\preprocessing\Create_embeddings\Rerank\rag_runtime_rerank.json",
    "--e5-query-prefix",
    "--rerank"
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
