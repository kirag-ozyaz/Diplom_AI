# Скрипты Tests24 (электробезопасность)

Выгрузка формулировок вопросов с [tests24.ru](https://tests24.ru/) для **дополнения** контрольного набора оценки RAG.  
Основной рабочий набор этапа 4 — **300 вопросов** в реестре `data/rag_eval_questions/eval_questions.json` (см. `scripts/stage4_eval/README.md`).

Каталог тестов и зеркало: [tests24.su — электробезопасность](https://tests24.su/test-24/elektrobezopasnost/).

| Скрипт | Назначение |
|--------|------------|
| `fetch_bilet.py` | Парсинг билета (`iter=4&bil=&test=`) → JSON в `data/tests24/` |
| `build_stage4_eval_questions.py` | Отбор вопросов по ПУЭ из `bilet_*.json` → реестр JSON (`--merge-base` объединяет с base38) |
| `paths.py` | Каталог данных `TESTS24_DATA` = `data/tests24` |
| `probe_links.py` | Отладка: ссылки с страницы выбора области (`iter=1&s_group=7`) |

Запуск из **корневого каталога проекта**:

```bash
python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
python scripts/tests24/build_stage4_eval_questions.py --merge-base -o data/rag_eval_questions/eval_questions_tests24.json
python scripts/tests24/probe_links.py
```

**Важно:** не запускайте `build_stage4_eval_questions.py` с выходом в основной `eval_questions.json`, если там уже утверждён набор из 300 вопросов; укажите отдельный файл через `-o`.

Подробнее: `manual/tests24_electro_safety.md`.
