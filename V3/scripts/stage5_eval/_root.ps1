function Get-V3Root {
    $current = Get-Item -LiteralPath $PSScriptRoot
    while ($null -ne $current) {
        if ((Test-Path -LiteralPath (Join-Path $current.FullName 'configs/v3_config.json')) -and (Test-Path -LiteralPath (Join-Path $current.FullName 'src/retrieval_v3'))) { return $current.FullName }
        $current = $current.Parent
    }
    throw 'Не найдена папка V3'
}
