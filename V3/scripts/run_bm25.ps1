. (Join-Path $PSScriptRoot 'stage5_eval/_root.ps1')
$V3Root = Get-V3Root
& python (Join-Path $V3Root 'scripts/v3_evaluation.py') '--variants' 'bm25' @args
exit $LASTEXITCODE
