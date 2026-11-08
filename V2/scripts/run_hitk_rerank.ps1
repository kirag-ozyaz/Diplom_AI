. (Join-Path $PSScriptRoot 'stage4_eval/_root.ps1')
$V2Root = Get-V2Root
& python (Join-Path $V2Root 'scripts/run_pipeline.py') 'evaluate' '--mode' 'rerank' @args
exit $LASTEXITCODE
