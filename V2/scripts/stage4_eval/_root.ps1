function Get-V2Root {
    $current = Get-Item -LiteralPath $PSScriptRoot
    while ($null -ne $current) {
        if ((Test-Path -LiteralPath (Join-Path $current.FullName 'configs/pipeline.json')) -and (Test-Path -LiteralPath (Join-Path $current.FullName 'src/retrieval_eval'))) { return $current.FullName }
        $current = $current.Parent
    }
    throw 'Не найдена папка V2'
}
