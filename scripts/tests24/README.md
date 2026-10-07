# Скрипты Tests24 (электробезопасность)

Выгрузка формулировок вопросов с [tests24.ru](https://tests24.ru/) для подготовки набора Hit@k.  
Каталог тестов и зеркало: [tests24.su — электробезопасность](https://tests24.su/test-24/elektrobezopasnost/).

| Скрипт | Назначение |
|--------|------------|
| `fetch_bilet.py` | Парсинг билета (`iter=4&bil=&test=`) → JSON в `data/tests24/` |
| `build_stage4_eval_questions.py` | ПУЭ-вопросы из `bilet_*.json` → `stage4_eval_questions.json` (`--merge-base`) |
| `paths.py` | `TESTS24_DATA` = `data/tests24` |
| `probe_links.py` | Отладка: ссылки с страницы выбора области (`iter=1&s_group=7`) |

Запуск из корня репозитория:

```bash
python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
python scripts/tests24/build_stage4_eval_questions.py --merge-base
python scripts/tests24/probe_links.py
```

Подробнее: `manual/tests24_electro_safety.md`.
