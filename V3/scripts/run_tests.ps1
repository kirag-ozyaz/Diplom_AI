. (Join-Path $PSScriptRoot 'stage5_eval/_root.ps1')
$V3Root = Get-V3Root
& python -m unittest discover -s (Join-Path $V3Root 'scripts/tests') -t $V3Root -v @args
exit $LASTEXITCODE
