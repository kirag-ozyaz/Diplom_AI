# Run Hit@1 / Hit@3 / Hit@5 eval (Milvus must be up).
# Usage: run_hitk.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

& $Python scripts\stage4_eval\eval_retrieval_hitk.py
exit $LASTEXITCODE
