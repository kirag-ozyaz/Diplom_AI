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
    & $Python scripts\start_milvus.py
    exit $LASTEXITCODE
}

if ($SkipOllama) {
    & $Python scripts\start_report_docker.py --skip-ollama
    exit $LASTEXITCODE
}

& $Python scripts\start_report_docker.py
exit $LASTEXITCODE
