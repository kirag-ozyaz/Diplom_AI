# Tests24 — каталог и выгрузки билетов (электробезопасность)

Сырые JSON с [tests24.ru](https://tests24.ru/) / каталог [tests24.su](https://tests24.su/test-24/elektrobezopasnost/).  
**Не** входят в отчёт этапа 4: только вспомогательный материал для формулировок вопросов.

| Файл | Назначение |
|------|------------|
| `catalog_electro.json` | Справочник тестов ЭБ |
| `bilet_<test>_bil_<n>.json` | Выгрузка `scripts/tests24/fetch_bilet.py` |

Сборка eval-набора (ПУЭ-вопросы из билетов + базовые 38 вопросов):

```powershell
python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
python scripts/tests24/build_stage4_eval_questions.py --merge-base
```

Результат: `Этапы/Reports/etap4/data/stage4_eval_questions.json`. Правила `expected_clause` — в `scripts/tests24/build_stage4_eval_questions.py` (`CLAUSE_RULES`). Базовые 38 — `stage4_eval_questions_base38.json`.

См. `manual/tests24_electro_safety.md`, `scripts/tests24/README.md`.
