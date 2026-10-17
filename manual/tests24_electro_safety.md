# Tests24 — билеты по электробезопасности (внешний источник вопросов)

Для дипломного RAG по **ПУЭ** билеты полезны как **реалистичные формулировки** вопросов (как на аттестации). Эталон для метрик поиска (Hit@k) задаётся вручную: поле `expected_clause` в реестре контрольных вопросов должно совпадать с пунктом в `data/chunked/` и в индексе Milvus.

**Основной набор для отчёта этапа 4:** 300 контрольных вопросов в `data/rag_eval_questions/eval_questions.json` (формат реестра: `n_questions`, массив `questions` с полями `query`, `expected_clause`, `section`). Источник — markdown-набор «Набор из 300 вопросов (ПУЭ)»; скрипты Tests24 — **дополнительный** канал формулировок, а не замена этого набора.

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

## Расположение файлов в проекте

| Путь | Назначение |
|------|------------|
| `scripts/tests24/` | Скрипты (`fetch_bilet.py`, `probe_links.py`, `paths.py`, `build_stage4_eval_questions.py`) |
| `data/tests24/` | JSON: каталог тестов, выгрузки билетов (вспомогательные данные) |
| `data/rag_eval_questions/eval_questions.json` | Рабочий реестр контрольных вопросов для Hit@k и generation (300 записей) |
| `data/rag_eval_questions/eval_questions_74.json` | Архивный снимок более раннего набора |

Путь к данным Tests24: `TESTS24_DATA` в `scripts/tests24/paths.py`.

---

## Выгрузка вопросов из билета

Из корневого каталога проекта:

```bash
python scripts/tests24/fetch_bilet.py --test 996 --bilet 1
```

или по URL:

```bash
python scripts/tests24/fetch_bilet.py --url "https://tests24.ru/?iter=4&bil=1&test=996"
```

Результат: `data/tests24/bilet_<test>_bil_<n>.json`  
Запись: `num`, `query`, `source`, `test_id`, `bilet`, `source_url`.

Дальше: отобрать вопросы с опорой на **ПУЭ**, проставить `expected_clause`, при необходимости добавить в отдельный JSON или в реестр после экспертной проверки, затем выполнить `python scripts/stage4_eval/eval_retrieval_hitk.py`.

**Важно:** многие вопросы ссылаются на ПТЭЭП, приказы Минтруда, а не только на ПУЭ — такие не подходят для Hit@k по одной базе ПУЭ без расширения индекса.

---

## Сборка вспомогательного eval-набора из Tests24

1. Выгрузить билеты: `python scripts/tests24/fetch_bilet.py --test 996 --bilet N` (в проекте могут храниться выгрузки `bil` 1–13 и др.).
2. Собрать JSON в **отдельный** файл, например:  
   `python scripts/tests24/build_stage4_eval_questions.py --merge-base -o data/rag_eval_questions/eval_questions_tests24.json` — объединяет 38 базовых вопросов и уникальные формулировки Tests24 только по ПУЭ (варианты ответов обрезаются).
3. Пересчитать метрики: `scripts/stage4_eval/run_hitk.ps1` и при необходимости `run_generation.ps1`, `run_perf_and_judge.ps1`.

Примеры эталонов в `CLAUSE_RULES` (`build_stage4_eval_questions.py`):

- приёмник электрической энергии → **1.2.7**;
- сечение алюминиевого заземляющего проводника к ГЗШ → **1.7.117**;
- вопросы не по ПУЭ (ПТЭЭП, приказы Минтруда и т.д.) в eval **не попадают**.

---

## Правовое использование

- Указывайте источник ([tests24.ru](https://tests24.ru/), [tests24.su](https://tests24.su/test-24/elektrobezopasnost/)) и учебную цель.
- Не публикуйте массовые дампы всей базы сайта — достаточно выборочных JSON из `data/tests24/`.

См. также: `manual/Hit_at_k.md` (§4), `scripts/stage4_eval/README.md`.
