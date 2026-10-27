# Summary table MRR/nDCG (auto paths) or bounds from Hit@k.
# Usage:
#   run_rank_metrics.ps1
#   run_rank_metrics.ps1 -FromHitk

param(
    [switch]$FromHitk
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

$rankScript = "scripts\stage4_eval\retrieval\mrr_ndcg\rank_metrics.py"

if ($FromHitk) {
    Write-Stage4Banner -Title "MRR/nDCG bounds from Hit@1/3/5" -Detail "rank_metrics.py --from-hitk --refresh-default"
    $pyArgs = @($rankScript, "--from-hitk", "--refresh-default")
} else {
    Write-Stage4Banner -Title "MRR / nDCG@k comparison" -Detail "rank_metrics.py --refresh-default"
    $pyArgs = @($rankScript, "--refresh-default")
}
Write-Stage4Log ('python ' + ($pyArgs -join ' '))
exit (Invoke-Stage4Python -ArgumentList $pyArgs)
