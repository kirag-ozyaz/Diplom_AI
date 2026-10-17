# Tests24 — каталог и выгрузки билетов (электробезопасность)

Сырые JSON с [tests24.ru](https://tests24.ru/) и каталог [tests24.su](https://tests24.su/test-24/elektrobezopasnost/).  
**Не** входят в основной отчёт этапа 4: это вспомогательный материал для подбора формулировок вопросов.

Рабочий контрольный набор для метрик RAG — **300** вопросов в `data/rag_eval_questions/eval_questions.json` (реестр JSON).

| Файл | Назначение |
|------|------------|
| `catalog_electro.json` | Справочник тестов ЭБ |
| `bilet_<test>_bil_<n>.json` | Выгрузка `scripts/tests24/fetch_bilet.py` |

Пример сборки **отдельного** набора из билетов (не перезаписывать основной файл из 300 вопросов):

```powershell
python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
python scripts/tests24/build_stage4_eval_questions.py --merge-base -o data/rag_eval_questions/eval_questions_tests24.json
```

Правила `expected_clause` для автоматического сопоставления — в `scripts/tests24/build_stage4_eval_questions.py` (`CLAUSE_RULES`). Базовые 38 вопросов — `eval_questions_base38.json`.

См. `manual/tests24_electro_safety.md`, `scripts/tests24/README.md`.
