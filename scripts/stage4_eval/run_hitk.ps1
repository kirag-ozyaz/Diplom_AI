# Run Hit@1 / Hit@3 / Hit@5 eval (Milvus must be up).
# Usage: run_hitk.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

Write-Stage4Banner -Title "Оценка retrieval Hit@k" -Detail "коллекция diplom_multimodal, eval_retrieval_hitk.py"
Write-Stage4Log "[*] Перед Fetching / Loading weights в логе будет «[*] Загрузка весов embedding»; затем прогресс [i/N]"
Write-Stage4Log "Команда: scripts\stage4_eval\retrieval\eval_retrieval_hitk.py"
exit (Invoke-Stage4Python -ArgumentList @("scripts\stage4_eval\retrieval\eval_retrieval_hitk.py"))
