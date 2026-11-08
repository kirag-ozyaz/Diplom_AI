. (Join-Path $PSScriptRoot '_root.ps1')
$V2Root = Get-V2Root
& python (Join-Path $V2Root 'scripts/run_pipeline.py') 'plan' @args
exit $LASTEXITCODE
