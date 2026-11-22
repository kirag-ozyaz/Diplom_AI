param([Parameter(Mandatory=$true)][string]$Question)
. (Join-Path $PSScriptRoot 'stage5_eval/_root.ps1')
$V3Root = Get-V3Root
& python (Join-Path $V3Root 'scripts/v3_ask.py') $Question @args
exit $LASTEXITCODE
