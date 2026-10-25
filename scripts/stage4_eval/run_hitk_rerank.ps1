# Run Hit@1 / Hit@3 / Hit@5 eval (коллекция diplom_multimodal_e5_rerank).
# Usage: run_hitk_rerank.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

Write-Stage4Banner -Title "Оценка retrieval Hit@k (опыт 2, реранкер)" -Detail "коллекция diplom_multimodal_e5_rerank, query: + rerank, eval_retrieval_hitk_rerank.py"
Write-Stage4Log "[*] Перед Fetching / Loading weights в логе будет «[*] Загрузка весов embedding»; затем реранкер и [1/N]"
Write-Stage4Log "Команда: scripts\stage4_eval\retrieval\eval_retrieval_hitk_rerank.py"
exit (Invoke-Stage4Python -ArgumentList @("scripts\stage4_eval\retrieval\eval_retrieval_hitk_rerank.py"))
