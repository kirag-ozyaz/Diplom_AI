# Общее: корень репозитория и Python для обёрток stage4_eval.
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot
$env:PYTHONIOENCODING = "utf-8"
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8
[Console]::InputEncoding = $utf8
$OutputEncoding = $utf8
if ($PSVersionTable.PSEdition -eq "Desktop") {
    chcp 65001 | Out-Null
}
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

. (Join-Path $PSScriptRoot "_banner.ps1")

if (-not $env:STAGE4_RUN_LOG) {
    $logDir = Join-Path $ProjectRoot "scripts\stage4_eval\results\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $env:STAGE4_RUN_LOG = Join-Path $logDir "stage4_$stamp.log"
}

if (-not $env:STAGE4_ROOT_LOGGED) {
    Write-Stage4Log "Корень проекта: $ProjectRoot"
    Write-Stage4Log "Python: $Python"
    Write-Stage4Log "Лог-файл: $env:STAGE4_RUN_LOG"
    $env:STAGE4_ROOT_LOGGED = "1"
}
