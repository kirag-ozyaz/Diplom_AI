# MRR и nDCG@k для retrieval (этап 4)

## Что считаем
Для каждого вопроса известен ожидаемый пункт ПУЭ (`expected_clause`); релевантность бинарная.
`rank` — позиция (1…k_max) первого чанка в выдаче, где найден пункт (та же проверка `clause_in_text`, что в `eval_retrieval_hitk*.py`); если не найден в top-k_max — `null`.

| Метрика | Смысл | Формула (N вопросов) |
|---|---|---|
| Hit@k | доля вопросов, где пункт есть в top-k | `(1/N)·Σ [rank ≤ k]` |
| MRR | насколько высоко стоит первый правильный ответ | `(1/N)·Σ 1/rank` (0, если не найден в top-k_max) |
| MRR@k | то же, но учитываются только позиции ≤ k | `(1/N)·Σ [rank ≤ k]/rank` |
| nDCG@k | качество ранжирования с логарифмическим штрафом за позицию | `DCG@k = Σ_{i≤k} rel_i / log2(i+1)`, `nDCG@k = DCG@k / IDCG@k` |

При одном релевантном пункте `nDCG@k = 1/log2(rank+1)` при `rank ≤ k`, иначе 0 (nDCG@1 = Hit@1).
Если `expected_clause` — список из m пунктов, `IDCG@k = Σ_{i≤min(m,k)} 1/log2(i+1)`, rank — первый найденный любой из пунктов (для nDCG рекомендуется флаг `--dedup`).

## Куда положить файлы
```
scripts/stage4_eval/retrieval/eval_retrieval_rank.py
scripts/stage4_eval/retrieval/rank_metrics.py
scripts/stage4_eval/retrieval/test_rank_metrics.py   (необязательно)
```
Результаты пишутся рядом с существующими: `scripts/stage4_eval/results/retrieval/stage4_rank_results_{base,e5,rerank}.json`. Старые `stage4_hitk_results*.json` не перезаписываются.

## Запуск (PowerShell, из корня проекта)
Ollama для retrieval не нужна, нужен только Milvus.
```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING = "utf-8"
python scripts\infra_start_system\start_milvus.py

# Опыт 1 — base (diplom_multimodal)
python scripts\stage4_eval\retrieval\eval_retrieval_rank.py --mode base
# Опыт 2 — E5 prefixes query:/passage: (diplom_multimodal_e5)
python scripts\stage4_eval\retrieval\eval_retrieval_rank.py --mode e5
# Опыт 3 — E5 + реранкер bge-reranker-v2-m3, ANN top-20 → top-10 (diplom_multimodal_e5_rerank)
python scripts\stage4_eval\retrieval\eval_retrieval_rank.py --mode rerank

# Сводная таблица (md + csv)
$R = "scripts\stage4_eval\results\retrieval"
python scripts\stage4_eval\retrieval\rank_metrics.py "$R\stage4_rank_results_base.json" "$R\stage4_rank_results_e5.json" "$R\stage4_rank_results_rerank.json" --out-dir $R

# Только границы по уже имеющимся Hit@1/3/5 (без Milvus)
python scripts\stage4_eval\retrieval\rank_metrics.py --from-hitk "$R\stage4_hitk_results.json" "$R\stage4_hitk_results_e5.json" "$R\stage4_hitk_results_rerank.json" --out-dir $R
```
Флаги: `--k-max 10` (глубина выдачи), `--ks 1,3,5,10`, `--questions <json>`, `--out <json>`, `--dedup`, `--limit-questions 5` (быстрая проверка).

``` метрики MRR и nDCG@k
Запустить Milvus и прогнать скрипт по очереди с --mode base, --mode e5 и --mode rerank.
После этого rank_metrics.py соберёт таблицу трёх опытов.
```

## Ожидаемый результат
- `stage4_rank_results_<mode>.json`: `metrics` (hit@k, mrr, mrr@k, ndcg@k в долях 0…1), `metrics_percent` (hit@k в %), `details[]` с `rank`, `rels`, `scores` по каждому из 268 вопросов.
- Hit@1/3/5 должны совпасть с `stage4_hitk_results*.json` (та же проверка и та же выдача; у реранкера top-5 из top-10 совпадает, т.к. кандидатов всё равно 20). Небольшие расхождения возможны из-за недетерминизма ANN/GPU.
- `rank_metrics_comparison.md/.csv` — таблица трёх опытов.

## Границы по старым Hit@k (до прогона)
Ранг известен только с точностью до корзины 1 / 2–3 / 4–5 / >5. Нижняя граница: худшая позиция в корзине (3, 5, не найден); верхняя: лучшая (2, 4, позиция 6).

| Эксперимент | MRR@5 | MRR (top-10) | nDCG@3 | nDCG@5 | nDCG@10 |
|---|---|---|---|---|---|
| Опыт 1 base | 0.652–0.685 | 0.652–0.716 | 0.672–0.695 | 0.692–0.718 | 0.692–0.784 |
| Опыт 2 E5 prefixes | 0.672–0.704 | 0.672–0.732 | 0.690–0.714 | 0.712–0.738 | 0.712–0.796 |
| Опыт 3 E5+rerank | 0.772–0.796 | 0.772–0.814 | 0.787–0.805 | 0.800–0.819 | 0.800–0.859 |

nDCG@1 = Hit@1 точно: 0.582 / 0.601 / 0.720.
