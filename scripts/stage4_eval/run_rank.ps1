# MRR / nDCG@k retrieval eval (Milvus must be up). Same RAG modes as Hit@k.
# Usage:
#   run_rank.ps1 -Mode base
#   run_rank.ps1 -Mode e5
#   run_rank.ps1 -Mode rerank
#   run_rank.ps1 -Mode base -LimitQuestions 5

param(
    [Parameter(Mandatory)]
    [ValidateSet("base", "e5", "rerank")]
    [string]$Mode,

    [int]$LimitQuestions = 0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

$detail = switch ($Mode) {
    "base"   { "diplom_multimodal, eval_retrieval_rank.py --mode base" }
    "e5"     { "diplom_multimodal_e5, query:/passage:, --mode e5" }
    "rerank" { "diplom_multimodal_e5_rerank, bge-reranker-v2-m3, --mode rerank" }
}

Write-Stage4Banner -Title "Retrieval MRR / nDCG@k ($Mode)" -Detail $detail
$scriptRel = "scripts\stage4_eval\retrieval\mrr_ndcg\eval_retrieval_rank.py"
$pyArgs = @($scriptRel, "--mode", $Mode)
if ($LimitQuestions -gt 0) {
    $pyArgs += @("--limit-questions", "$LimitQuestions")
}
Write-Stage4Log ('python ' + ($pyArgs -join ' '))
exit (Invoke-Stage4Python -ArgumentList $pyArgs)
