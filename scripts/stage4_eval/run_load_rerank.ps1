# Заливка коллекции опыта 2: diplom_multimodal_e5_rerank (passage:).
# Не трогает diplom_multimodal и diplom_multimodal_e5.
# Usage: run_load_rerank.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_root.ps1")

Write-Stage4Banner -Title "Заливка коллекции опыта 2 (реранкер)" -Detail "load_data_rerank.py → diplom_multimodal_e5_rerank, prefix passage:"
Write-Stage4Log "Команда: src\preprocessing\Create_embeddings\Rerank\load_data_rerank.py"
exit (Invoke-Stage4Python -ArgumentList @("src\preprocessing\Create_embeddings\Rerank\load_data_rerank.py"))
