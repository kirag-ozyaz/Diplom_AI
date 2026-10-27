# MRR / nDCG@k — прогон и артефакты (этап 4)

**Теория, формулы, как читать MRR рядом с Hit@k:** `manual/mrr_ndcg.md`.

Этот файл — **как устроен расчёт в репозитории** и что получается после прогона.

---

## 1. Что делает пайплайн

1. Для каждого вопроса из `eval_questions.json` выполняется `search_text` в Milvus (как в Hit@k, но глубина **top-10** по умолчанию).
2. По выдаче ищется **первый** чанк, где есть `expected_clause` → записывается **rank** (1…10 или «не найден»).
3. По всем вопросам считаются Hit@k, MRR, MRR@k, nDCG@k → один JSON на опыт (`base` / `e5` / `rerank`).
4. Когда лежат **все три** JSON, `rank_metrics.py` собирает общую таблицу `rank_metrics_comparison.md` / `.csv`.
5. При полном наборе JSON может обновиться блок MRR в `Readme-4.md` §5.4 (через `update_readme4_eval_docs`, как после Hit@k).

Hit@1/3/5 в rank-JSON **должны совпасть** с `stage4_hitk_results*.json` при тех же коллекциях: та же проверка пункта, тот же поиск (у реранкера top-5 для Hit@k — подмножество top-10 после реранка).

**В общем прогоне:** после Hit@k автоматически идёт rank для того же опыта — шаг `[3/6]` в `run_all.ps1` (base), `run_all_e5.ps1` (e5), `run_all_rerank.ps1` (rerank). Сводка `rank_metrics_comparison.*` собирается, когда на диске есть все три `stage4_rank_results_*.json` (после трёх полных прогонов или `run_rank_all.ps1`).

**Отдельно:** `run_rank_all.ps1` — все три режима rank подряд без generation (~7 мин Milvus), если нужно пересчитать только retrieval.

---

## 2. Файлы в репозитории

| Путь | Назначение |
|------|------------|
| `eval_retrieval_rank.py` | Прогон одного опыта, запись JSON |
| `rank_metrics.py` | Сводная таблица трёх опытов или **границы** по старым Hit@k |
| `test_rank_metrics.py` | Unit-тесты формул (без Milvus) |
| `run_rank.ps1` | Обёртка: один `--mode` |
| `run_rank_all.ps1` | infra (опционально) + base + e5 + rerank + сводка |
| `run_rank_metrics.ps1` | Только пересборка таблицы из готовых JSON |

**Артефакты** (не коммитить лишнее по желанию, но пути фиксированы):

- `scripts/stage4_eval/results/retrieval/stage4_rank_results_{base,e5,rerank}.json`
- `rank_metrics_comparison.md`, `rank_metrics_comparison.csv`
- `rank_metrics_bounds_from_hitk.md` — оценочные границы, если есть только Hit@1/3/5 (без нового прогона rank)

`stage4_hitk_results*.json` **не перезаписываются**.

---

## 3. Три режима (`--mode`)

Соответствуют трём контурам Hit@k на реестре 268:

| Режим | Коллекция | Особенности |
|-------|-----------|-------------|
| `base` | `diplom_multimodal` | Без префиксов E5 |
| `e5` | `diplom_multimodal_e5` | Префиксы `query:` / `passage:` |
| `rerank` | `diplom_multimodal_e5_rerank` | E5 + ANN top-20 → реранкер → top-10 в метрике |

Параметры по умолчанию: `--k-max 10`, `--ks 1,3,5,10`. Для отладки: `--limit-questions 5`. Отключить обновление Readme: `--no-refresh-readme`.

---

## 4. Запуск (PowerShell, корень проекта)

Нужен **Milvus**; **Ollama не нужна**.

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING = "utf-8"

# Всё сразу: три опыта + сводная таблица
.\scripts\stage4_eval\run_rank_all.ps1

# Milvus уже запущен
.\scripts\stage4_eval\run_rank_all.ps1 -SkipInfra

# Один опыт
.\scripts\stage4_eval\run_rank.ps1 -Mode rerank

# Быстрая проверка (5 вопросов)
.\scripts\stage4_eval\run_rank.ps1 -Mode base -LimitQuestions 5

# Только пересобрать comparison из готовых JSON
.\scripts\stage4_eval\run_rank_metrics.ps1

# Оценочные границы MRR/nDCG из Hit@1/3/5 без Milvus
.\scripts\stage4_eval\run_rank_metrics.ps1 -FromHitk
```

Прямой Python:

```powershell
python scripts\stage4_eval\retrieval\mrr_ndcg\eval_retrieval_rank.py --mode base
python scripts\stage4_eval\retrieval\mrr_ndcg\rank_metrics.py --refresh-default
```

Тесты:

```powershell
cd scripts\stage4_eval\retrieval\mrr_ndcg
python test_rank_metrics.py
```

---

## 5. Автообновление (что срабатывает само)

| Событие | Результат |
|---------|-----------|
| Завершился `eval_retrieval_rank.py` | Записан `stage4_rank_results_<mode>.json` |
| Есть все три rank JSON | Пересобраны `rank_metrics_comparison.*` |
| Полный набор rank JSON + не `--no-refresh-readme` | Вызов `update_readme4_eval_docs` → §5.4 в Readme-4 |
| Запуск `update_readme4_eval_docs` после Hit@k | Сводка rank тоже пересобирается, если JSON на месте |

---

## 6. Последний зафиксированный прогон (*N* = 268, 28.10.2026)

Источник истины: JSON и `rank_metrics_comparison.md` в `results/retrieval/`. Краткая выжимка:

| Опыт | MRR | MRR@5 | nDCG@5 | nDCG@10 |
|------|-----|-------|--------|---------|
| base | 0.681 | 0.673 | 0.708 | 0.729 |
| E5 | 0.696 | 0.690 | 0.726 | 0.743 |
| E5+rerank | 0.793 | 0.787 | 0.812 | 0.826 |

Hit@1/3/5 совпали с `stage4_hitk_results*.json`. Реранкер даёт наибольший скачок по **MRR** (+0,10 к E5) — см. разбор в `manual/mrr_ndcg.md` §7.

**Границы без Milvus:** если есть только Hit@1/3/5, rank известен с точностью до корзин (1 / 2–3 / 4–5 / >5). Тогда `run_rank_metrics.ps1 -FromHitk` пишет `rank_metrics_bounds_from_hitk.md` — это **не** точные MRR, а интервал возможных значений.
