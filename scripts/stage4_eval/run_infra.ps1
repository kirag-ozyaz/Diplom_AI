# Start Docker services for stage-4 metrics.
# Usage:
#   run_infra.ps1              # Milvus + Ollama (start_report_docker.py)
#   run_infra.ps1 -MilvusOnly  # Hit@k only
#   run_infra.ps1 -SkipOllama  # Milvus via start_report_docker --skip-ollama

param(
    [switch]$MilvusOnly,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

if ($MilvusOnly) {
    Write-Stage4Banner -Title "Подготовка инфраструктуры (Docker)" -Detail "Только Milvus (start_milvus.py)"
} elseif ($SkipOllama) {
    Write-Stage4Banner -Title "Подготовка инфраструктуры (Docker)" -Detail "Milvus + пропуск Ollama (--skip-ollama)"
} else {
    Write-Stage4Banner -Title "Подготовка инфраструктуры (Docker)" -Detail "Milvus и Ollama (start_report_docker.py)"
}

if ($MilvusOnly) {
    Write-Stage4Log "Команда: start_milvus.py"
    exit (Invoke-Stage4Python @("scripts\infra_start_system\start_milvus.py"))
}

if ($SkipOllama) {
    Write-Stage4Log "Команда: start_report_docker.py --skip-ollama"
    exit (Invoke-Stage4Python @("scripts\infra_start_system\start_report_docker.py", "--skip-ollama"))
}

Write-Stage4Log "Команда: start_report_docker.py"
exit (Invoke-Stage4Python @("scripts\infra_start_system\start_report_docker.py"))
