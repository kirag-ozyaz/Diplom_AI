# Tests24 — билеты по электробезопасности (внешний источник вопросов)

Для дипломного RAG по **ПУЭ** билеты полезны как **реалистичные формулировки** вопросов (как на аттестации). Эталон Hit@k в проекте задаётся вручную: `expected_clause` в `stage4_eval_questions.json` должен совпадать с пунктом в `data/chunked/` / Milvus.

## Два сайта одного семейства «Тест 24»

| Сайт | Назначение |
|------|------------|
| [tests24.ru](https://tests24.ru/) | Интерактивные тесты, билеты, параметры `iter`, `test`, `bil` |
| [tests24.su — электробезопасность](https://tests24.su/test-24/elektrobezopasnost/) | Каталог тестов ЭБ (ЭБ 1254.20–1260, архив, ЭТЛ и др.) с описаниями |

На **tests24.ru** проходят билеты; на **tests24.su** удобно выбрать нужный код теста (например ЭБ 1256.21, III группа), затем открыть тот же тест на tests24.ru через раздел электробезопасности.

---

## Навигация на tests24.ru

| Шаг | URL (пример) | Что выбираете |
|-----|----------------|---------------|
| Раздел «Электробезопасность» | `https://tests24.ru/?iter=1&s_group=7` | [Область аттестации](https://tests24.ru/?iter=1&s_group=7) |
| Список тестов в области | `https://tests24.ru/?iter=2&group=1` | ЭБ 1254.20 и др. |
| Выбор билета | `https://tests24.ru/?iter=3&test=996` | Билет №1 … №N |
| Прохождение билета | `https://tests24.ru/?iter=4&bil=1&test=996` | Вопросы с вариантами |

Полный каталог групп: `https://tests24.ru/?iter=6`.

### Области (`iter=2&group=…`)

Справочник `group` → название: `data/tests24/catalog_electro.json` (поле `tests24_ru_groups`).

---

## Структура в репозитории

| Путь | Назначение |
|------|------------|
| `scripts/tests24/` | Скрипты (`fetch_bilet.py`, `probe_links.py`, `paths.py`) |
| `data/tests24/` | JSON: каталог тестов, выгрузки билетов (не в отчёте этапа 4) |
| `Этапы/Reports/etap4/data/stage4_eval_questions.json` | Набор Hit@k (после ручной разметки `expected_clause`) |

Путь к данным: `TESTS24_DATA` в `scripts/tests24/paths.py`.

---

## Выгрузка вопросов из билета

Из корня репозитория:

```bash
python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
```

или по URL:

```bash
python scripts/tests24/fetch_bilet.py --url "https://tests24.ru/?iter=4&bil=1&test=996"
```

Результат: `data/tests24/bilet_<test>_bil_<n>.json`  
Запись: `num`, `query`, `source`, `test_id`, `bilet`, `source_url`.

Дальше: отобрать вопросы с опорой на **ПУЭ**, проставить `expected_clause`, добавить в `stage4_eval_questions.json`, прогнать `python scripts/stage4_eval/eval_retrieval_hitk.py`.

**Важно:** многие вопросы ссылаются на ПТЭЭП, приказы Минтруда, а не только на ПУЭ — такие не подходят для Hit@k по одной базе ПУЭ без расширения индекса.

---

## Сборка eval-набора этапа 4

1. Выгрузить билеты: `python scripts/tests24/fetch_bilet.py --test 996 --bilet N` (в репозитории уже есть `bil` 1–10).
2. Собрать JSON: `python scripts/tests24/build_stage4_eval_questions.py --merge-base` — остаются **38** исходных вопросов + **уникальные** формулировки Tests24 только по ПУЭ (варианты ответов обрезаются).
3. Пересчитать метрики: `scripts/stage4_eval/run_hitk.ps1` и при необходимости `run_generation.ps1`.

Примеры эталонов в `CLAUSE_RULES` (`build_stage4_eval_questions.py`):

- приёмник электрической энергии → **1.2.7**;
- сечение алюминиевого заземляющего проводника к ГЗШ → **1.7.117**;
- вопросы не по ПУЭ (ПТЭЭП, приказы Минтруда и т.д.) в eval **не попадают**.

---

## Правовое использование

- Указывайте источник ([tests24.ru](https://tests24.ru/), [tests24.su](https://tests24.su/test-24/elektrobezopasnost/)) и учебную цель.
- Не коммитьте массовые дампы всей базы сайта — достаточно выборочных JSON из `data/tests24/`.

См. также: `manual/Hit_at_k.md` (§4).
