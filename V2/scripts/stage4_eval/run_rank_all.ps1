param([Parameter(Mandatory=$true)][string[]]$Inputs)
. (Join-Path $PSScriptRoot '_root.ps1')
$V2Root = Get-V2Root
foreach ($InputFile in $Inputs) {
    & python (Join-Path $V2Root 'scripts/run_pipeline.py') evaluate --input $InputFile
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
