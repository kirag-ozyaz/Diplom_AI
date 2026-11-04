# Автоматическая сводка метрик этапа 4

## Зачем
Сейчас сводные таблицы по трём опытам (`Etap4-hitk-svod.md`, `docs/Сводка_метрик_этапа_4.md`, сравнение в `Readme-4.md`) заполняются вручную. Автоматически собирается только сравнение MRR/nDCG (`rank_metrics.py`) и блоки `Readme-4.md` для одного опыта (база). Скрипт `build_stage4_summary.py` собирает все слои метрик по трём опытам из готовых JSON одним запуском.

## Что делает
Читает `scripts/stage4_eval/results/`:

| Слой | Файлы (опыт 1 / 2 / 3) |
|---|---|
| Hit@k | `retrieval/stage4_hitk_results.json`, `_e5`, `_rerank` |
| MRR, nDCG@k, Hit@10 | `retrieval/stage4_rank_results_base.json`, `_e5`, `_rerank` |
| Генерация (citation, groundedness, relevance, время) | `generation/stage4_gen_eval_results.json`, `_e5`, `_rerank` |
| Нагрузочный тест | `generation/stage4_performance_metrics.json`, `_e5`, `_rerank` |
| LLM-as-a-Judge | `generation/stage4_llm_judge_metrics.json`, `_e5`, `_rerank` |

Пишет в `scripts/stage4_eval/results/`:
- `stage4_summary.md` — таблицы для отчёта;
- `stage4_summary.csv` — длинная таблица (опыт; слой; метрика; значение; файл-источник; дата прогона), разделитель `;`, открывается в Excel;
- `stage4_summary.json`.

Проверки (раздел «Проверки» в md):
- generation посчитан не на всех вопросах (`partial_run` или N ≠ N в Hit@k) — значения помечаются ⚠;
- Hit@1/3/5 в `stage4_hitk_results*` и `stage4_rank_results_*` не совпадают;
- `citation_in_context_rate` ≠ Hit@5;
- сбои вызова LLM-judge (в среднее попали нули).

Milvus, Ollama и `scripts/lib` не нужны, только Python 3.9+ без внешних пакетов.

## Установка
```
scripts/stage4_eval/reports/build_stage4_summary.py
scripts/stage4_eval/run_summary.ps1
```

## Запуск (из корня проекта)
```powershell
python scripts\stage4_eval\reports\build_stage4_summary.py
# или
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_summary.ps1
# код выхода 1 при замечаниях (для run_all):
python scripts\stage4_eval\reports\build_stage4_summary.py --strict
```
Параметры: `--root <корень проекта>`, `--out-dir <папка>`, `--strict`.

Чтобы сводка обновлялась после каждого полного прогона, добавить последним шагом в `run_all.ps1`, `run_all_e5.ps1`, `run_all_rerank.ps1`, `run_rank_all.ps1`:
```powershell
& (Join-Path $here "run_summary.ps1")
```

## Проверено
На файлах из папки проекта (Google Drive, 28.10.2026). Результат — `primer_stage4_summary.md`. Все значения совпали с отчётом этапа 4 (версия 2), кроме генерации опыта 1: файл `stage4_gen_eval_results.json` перезаписан неполным прогоном (39 вопросов, 25.10.2026 20:05), скрипт помечает его ⚠. Найден также сбой LLM-judge в опыте 3 (вопрос id=178).

## Что ещё исправить в проекте (вручную)
1. Повторить полный прогон генерации опыта 1: `run_generation.ps1 -Mode live` (без `--limit`).
2. Пробные прогоны с `--limit` писать в отдельный файл: `eval_rag_generation.py --limit 5 --out ...\stage4_gen_eval_results_test.json`. Лучше изменить скрипт: при `--limit` без явного `--out` добавлять суффикс `_partial`.
3. `update_readme4_eval_docs.py`: не брать в `Readme-4.md` генерацию с `partial_run`; убрать жёстко заданную дату `**Дата отчёта:** 18.10.2026`.
4. Папка `scripts/lib` (`_bootstrap.py`, `report_paths.py`, `notebook_bootstrap.py`, `eval_questions_io.py`) не попадает в репозиторий и на Диск из-за строки `lib/` в `.gitignore`. Без неё не запускаются скрипты оценки, `update_readme4_eval_docs.py`, `stage4_hitk_report.py` и ноутбук. Добавить в `.gitignore` исключение `!scripts/lib/`.
5. `Etap4-hitk-svod.md` и `docs/Сводка_метрик_этапа_4.md` вести как ссылку на `stage4_summary.md` или собирать из него, а не править числа вручную.
