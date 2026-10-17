# Этап 4 — сбор метрик качества RAG (Hit@k и generation)

Данный каталог объединяет скрипты **оценки** прототипа RAG по Правилам устройства электроустановок (ПУЭ): измерение качества **поиска фрагментов** (метрики Hit@1, Hit@3, Hit@5) и качества **генерации ответа** языковой моделью (цитирование нормы, опора на контекст, релевантность). Скрипты запуска контейнеров Docker (Milvus, Ollama) расположены на уровень выше — в каталоге `scripts/`.

Все команды ниже выполняются **из корневого каталога проекта** (каталог с `scripts/`, `config/`, `Этапы/`). Рекомендуется активировать виртуальное окружение:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## Назначение каталога и состав файлов

| Файл | Назначение |
|------|------------|
| `README.md` | Руководство по прогону метрик (этот документ) |
| `_bootstrap.py` | Определение корня проекта и настройка `sys.path` для Python-скриптов |
| `_root.ps1` | Определение корня проекта и интерпретатора Python для сценариев PowerShell |
| `eval_retrieval_hitk.py` | Расчёт Hit@1 / Hit@3 / Hit@5 по Milvus и модели эмбеддингов (без LLM) |
| `eval_rag_generation.py` | Расчёт метрик generation в режимах `live`, `mock`, `dry-run` |
| `update_readme4_eval_docs.py` | Обновление разделов §5.3, §6.1 и §7 в `Readme-4.md` по сохранённому JSON |
| `stage4_hitk_report.py` | Формирование текстовых блоков отчёта Hit@k для Word и ноутбука |
| `plot_stage4_hitk.py` | Построение графиков Hit@k (PNG для отчёта, Plotly для ноутбука) |
| `stage4_hitk_notebook.py` | Вызов прогона и отображение результатов в ячейках §5.2 и §5.3 ноутбука |
| `demo_stage4_milvus_search.py` | Демонстрация одного семантического поиска (`search_text`) — раздел §6 ноутбука |
| `run_infra.ps1` | Запуск Docker-сервисов (Milvus и/или Ollama) |
| `run_hitk.ps1` | Запуск `eval_retrieval_hitk.py` |
| `run_generation.ps1` | Запуск `eval_rag_generation.py` с параметрами |
| `run_all.ps1` | Последовательный запуск: инфраструктура → Hit@k → generation (live) |
| `eval_rag_performance.py` | Эксплуатационные метрики (задержка, TTFT, пропускная способность) |
| `eval_rag_llm_judge.py` | Оценка генерации методом LLM-as-a-Judge (faithfulness, relevancy, context recall) |
| `run_perf_and_judge.ps1` | Последовательный запуск performance и LLM-judge |
| `print_run_done.py` | Сообщение об окончании цепочки прогонов |

**Дополнительные материалы проекта:**

- теория метрики Hit@k — `manual/Hit_at_k.md`;
- текст отчёта этапа 4 — `Этапы/Reports/etap4/Readme-4.md`;
- исполняемый ноутбук — `Этапы/Reports/etap4/Readme-4 (ver. 2).ipynb`;
- единые пути к артефактам в коде — `scripts/lib/report_paths.py`;
- пояснение к прогону generation — `scripts/stage4_eval/results/generation/Etap4-gen-metrics.md`.

---

## Зачем выполняется сбор метрик

На четвёртом этапе дипломного проекта требуется показать **рабочий контур RAG** и **первую количественную оценку** его компонентов.

**Retrieval (Hit@k).** Для каждого контрольного вопроса — один семантический поиск в Milvus. Успех: эталонный пункт ПУЭ (`Clause`) встречается в top-*k* чанков. Ollama **не используется**.

**Generation (`eval_rag_generation.py`).** Полный RAG (режим `live`) или имитация (`mock`). Метрики: **citation rate** (доля с эталонным пунктом в ответе/контексте), **groundedness** (опора ответа на контекст), **relevance** (соответствие эталону). Опционально `--llm-judge`.

**Эксплуатация (`eval_rag_performance.py`).** Нагрузочный прогон к Ollama: **TTFT**, **TPS**, задержка (средняя, p95, p99), **RPS**, **availability**.

**LLM-as-a-Judge (`eval_rag_llm_judge.py`).** Судья (модель из конфигурации) выставляет **faithfulness**, **answer relevancy**, **context recall** по каждому вопросу. См. ограничение методики в `scripts/stage4_eval/Сводка_метрик_этапа_4.md`.

**Сводка всех слоёв и последние сохранённые значения:** `scripts/stage4_eval/Сводка_метрик_этапа_4.md`; таблица для Word — §5.4 в `Этапы/Reports/etap4/Readme-4.md`.

**Результаты** — в `scripts/stage4_eval/results/retrieval/` и `generation/`.

### Реестр контрольных вопросов (300 записей)

Основной файл для Hit@k, generation, performance и LLM-judge:

`data/rag_eval_questions/eval_questions.json`

Структура — **реестр** (не плоский массив):

| Поле верхнего уровня | Назначение |
|----------------------|------------|
| `title` | Название набора |
| `source_file` | Исходный документ или путь к нему |
| `n_questions` | Число контрольных вопросов (сейчас **300**) |
| `questions` | Массив записей |

| Поле в записи `questions[]` | Назначение |
|-------------------------------|------------|
| `id` | Порядковый номер в наборе |
| `registry_id` | Стабильный идентификатор (например `Q-001`) |
| `query` | Текст вопроса |
| `expected_clause` | Эталонный пункт ПУЭ (поле Clause в индексе) |
| `section` | Раздел ПУЭ (для отчётов и срезов) |

Дополнительные копии и снимки (архив, не подменяют основной файл без явного решения):

| Файл | Назначение |
|------|------------|
| `eval_questions_pue300.json` | Полный реестр 300 вопросов (источник — markdown-набор ПУЭ) |
| `eval_questions_74.json` | Снимок раннего набора (~74 вопроса) |
| `eval_questions_base38.json` | Базовые 38 вопросов |

Чтение и запись реестра в коде: `eval_questions_io.py`. Дополнительные формулировки можно готовить по билетам электробезопасности (`manual/tests24_electro_safety.md`, `data/tests24/`); скрипт `build_stage4_eval_questions.py` **перезаписывает** основной файл при `--merge-base` и не должен запускаться поверх уже утверждённого набора из 300 вопросов без указания другого пути `-o`.

---

## Предварительные условия

1. Установлен и запущен **Docker Desktop** (для Milvus; для live generation — также контейнер Ollama).
2. В Milvus загружена коллекция с эмбеддингами чанков ПУЭ. Если база пуста или была сброшена:

   ```powershell
   python src\preprocessing\Create_embeddings\load_data.py
   ```

3. Файл `config/rag_runtime.json` согласован с вашим оборудованием (устройство для эмбеддингов `device_text`, имя модели Ollama `ollama.model` и др.).

**Проверка окружения (рекомендуется перед первым прогоном):**

```powershell
python scripts\compute_detect.py
python scripts\compute_detect.py --apply-config
powershell -ExecutionPolicy Bypass -File scripts\test_cudo.ps1
```

**Проверка состояния Milvus** после запуска контейнеров:

```powershell
cd infra\milvus
docker compose ps
```

Сервис `milvus-standalone` должен находиться в состоянии `healthy`; на `localhost` должен отвечать порт **19530**.

---

## Режимы оценки generation

| Режим | Milvus | Ollama | Назначение |
|-------|--------|--------|------------|
| `live` | да | да | Полный контур RAG, как в эксплуатации бота |
| `mock` | нет | нет | Офлайн-оценка по файлам `data/chunked/`; при наличии JSON Hit@k учитывается попадание в top-5 |
| `dry-run` | нет | нет | То же поведение, что у `mock` (синоним в CLI) |

Если при запросе `live` один из сервисов недоступен, скрипт фиксирует причину в поле `blockers` и может перейти в `mock`. Итоговый режим указан в `mode_effective` в файле результатов.

---

## Параметры сценариев PowerShell

### `run_infra.ps1`

| Вызов | Действие |
|-------|----------|
| без параметров | `python scripts\start_report_docker.py` — Milvus и Ollama |
| `-MilvusOnly` | `python scripts\start_milvus.py` — только Milvus (достаточно для Hit@k) |
| `-SkipOllama` | `python scripts\start_report_docker.py --skip-ollama` |

### `run_generation.ps1`

| Параметр | Описание |
|----------|----------|
| `-Mode live` | Режим по умолчанию: полный RAG |
| `-Mode mock` | Офлайн без Docker |
| `-StartId N` | Обработать только вопросы с полем `id` ≥ N (для продолжения прерванного прогона) |
| `-Limit N` | Ограничить число вопросов |
| `-LlmJudge` | Дополнительная оценка ответа через Ollama (только `live`, увеличивает время) |

### `run_all.ps1`

Основной способ полного прогона метрик (эквивалент `run_infra` → `run_hitk` → `run_generation -Mode live`).

| Параметр | Описание |
|----------|----------|
| без параметров | Инфраструктура → Hit@k → generation (`live`) |
| `-MilvusOnlyHitk` | После Hit@k этап generation не выполняется |
| `-SnapshotMilvusLogs` | В конце (или при ошибке infra/Hit@k/generation) вызвать `start_milvus_logs.py` |

Отдельно `python scripts/infra/start_milvus.py` и ручная цепочка Python нужны только если вы **не** используете PowerShell-сценарии. Если generation оборвался на середине (в JSON есть `error`, Milvus «упал»), но `run_all` уже завершился с кодом 0 — снимок логов вручную: `python scripts/infra/start_milvus_logs.py` (см. `infra/milvus/Storage.md`).

---

## Подробные команды Python

### Подготовка инфраструктуры (`scripts/`)

Запуск Milvus и Ollama одной командой (как в ноутбуке этапа 4):

```powershell
python scripts\start_report_docker.py
```

Только векторная база Milvus (оценка Hit@k, демонстрация поиска):

```powershell
python scripts\start_milvus.py
```

Сервер Ollama с загрузкой модели из конфигурации (для live generation):

```powershell
python scripts\start_ollama.py --pull
```

### Оценка retrieval (Hit@k)

```powershell
python scripts\stage4_eval\eval_retrieval_hitk.py
```

По завершении успешного прогона:

- создаются или обновляются `stage4_hitk_results.json`, `stage4_hitk_chart.png`, `stage4_hitk_report.png` в `scripts/stage4_eval/results/retrieval/`;
- в `stage4_hitk_runs.jsonl` добавляется запись истории;
- в `Этапы/Reports/etap4/Readme-4.md` обновляется блок §5.3.

Если автоматическое обновление отчёта не выполнилось:

```powershell
python scripts\stage4_eval\update_readme4_eval_docs.py
```

Синхронизация текста ячеек ноутбука с `Readme-4.md`:

```powershell
python scripts\sync_readme4_notebook.py
```

### Оценка generation

Полный прогон с Milvus и Ollama:

```powershell
python scripts\stage4_eval\eval_rag_generation.py --mode live
```

С дополнительной оценкой через LLM-judge:

```powershell
python scripts\stage4_eval\eval_rag_generation.py --mode live --llm-judge
```

Офлайн без Docker:

```powershell
python scripts\stage4_eval\eval_rag_generation.py --mode mock
```

Ограничение числа вопросов (отладка):

```powershell
python scripts\stage4_eval\eval_rag_generation.py --mode live --limit 5
```

Продолжение прерванного live-прогона (обрабатываются вопросы с `id` не меньше указанного; итоговый JSON перезаписывается по обработанному подмножеству — для полного отчёта по всем вопросам рекомендуется сохранить резервную копию файла результатов или выполнить полный прогон заново):

```powershell
python scripts\stage4_eval\eval_rag_generation.py --mode live --start-id 23
```

Указание пути к файлу результатов:

```powershell
python scripts\stage4_eval\eval_rag_generation.py --mode live --out путь\к\файлу.json
```

### Демонстрация поиска

```powershell
python scripts\stage4_eval\demo_stage4_milvus_search.py
```

---

## Выходные файлы

| Назначение | Путь |
|------------|------|
| Реестр контрольных вопросов (300) | `data/rag_eval_questions/eval_questions.json` |
| Последний прогон Hit@k (JSON) | `scripts/stage4_eval/results/retrieval/stage4_hitk_results.json` |
| История всех прогонов Hit@k | `scripts/stage4_eval/results/retrieval/stage4_hitk_runs.jsonl` |
| Столбчатая диаграмма Hit@k | `scripts/stage4_eval/results/retrieval/stage4_hitk_chart.png` |
| Сводный график для Word | `scripts/stage4_eval/results/retrieval/stage4_hitk_report.png` |
| Метрики generation | `scripts/stage4_eval/results/generation/stage4_gen_eval_results.json` |
| Эксплуатационные метрики (performance) | `scripts/stage4_eval/results/generation/stage4_performance_metrics.json` |
| Метрики LLM-as-a-Judge | `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics.json` |
| Текстовое пояснение к generation | `scripts/stage4_eval/results/generation/Etap4-gen-metrics.md` |

В файле generation имеет смысл проверить поля `mode_effective`, `blockers`, `metrics.n_questions` и `metrics.partial_run` (при значении `true` обработаны не все 300 контрольных вопросов). Текст отчёта для диплома: `Этапы/Reports/etap4/Readme-4.md` (числа — из JSON в `results/`).

---

## Связанные скрипты в каталоге `scripts/`

| Скрипт | Назначение |
|--------|------------|
| `scripts/lib/report_paths.py` | Константы путей к артефактам этапа 4 |
| `start_milvus.py`, `start_milvus_logs.py`, `start_ollama.py`, `start_report_docker.py` | Milvus/Ollama: запуск compose и снимок логов Milvus |
| `compute_detect.py` | Выбор GPU/CPU и запись `rag_runtime.json` |
| `test_cudo.ps1` | Проверка CUDA, Docker NVIDIA runtime и Ollama |
| `sync_readme4_notebook.py` | Копирование разделов из `Readme-4.md` в ноутбук |
| `notebook_bootstrap.py` | Инициализация путей в первой ячейке ноутбука |
| `test_rag_ollama.py` | Ручная проверка одного ответа RAG |

---

## Типичные затруднения и действия

| Наблюдаемое поведение | Рекомендуемое действие |
|------------------------|-------------------------|
| Сообщение о недоступности Milvus | Запустить `start_milvus.py`, дождаться `healthy`, порт 19530; сразу после сбоя — `start_milvus_logs.py` (см. `infra/milvus/Storage.md`) |
| В JSON generation указан режим `mock` при запросе `live` | Запустить Milvus и Ollama; просмотреть список `blockers` |
| Длительная пауза после старта Hit@k или live generation | При первом запуске загружаются PyTorch и модель эмбеддингов (до нескольких минут) — это ожидаемо |
| Прерывание прогона generation на середине набора | Перезапустить Milvus при сбое контейнера; продолжить с `--start-id` или выполнить полный прогон |
| `partial_run: true` | Завершить обработку оставшихся вопросов или повторить полный live-прогон |
| Ошибка CUDA в PyTorch | Выполнить `compute_detect.py --apply-config` или установить сборку torch с CUDA (см. `start/Readme.md`) |
| Раздел §5.3 в Readme-4 не изменился | Запустить `update_readme4_eval_docs.py` |

---

## Полный прогон метрик: два способа

Ниже приведены эквивалентные по смыслу последовательности: **пошаговые команды Python** (наглядно для отчёта и отладки) и **сценарии PowerShell** из этого каталога (удобно для повторяемого запуска).

### Способ 1 — команды Python (из корневого каталога проекта)

Рекомендуемая последовательность для полного набора метрик retrieval и generation в режиме live:

```powershell
python scripts\start_milvus.py
python scripts\start_ollama.py --pull
python scripts\stage4_eval\eval_retrieval_hitk.py
python scripts\stage4_eval\eval_rag_generation.py --mode live
```

**Альтернатива для инфраструктуры:** вместо двух первых строк можно один раз выполнить `python scripts\start_report_docker.py` (Milvus и Ollama), затем те же две команды оценки из каталога `stage4_eval`.

После изменения файла вопросов имеет смысл снова выполнить прогон Hit@k; при необходимости обновить ноутбук — `python scripts\sync_readme4_notebook.py`.

### Способ 2 — сценарии PowerShell (`scripts/stage4_eval/`)

Один сценарий на всю цепочку:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_all.ps1
```

Тот же порядок по шагам (с явным контролем каждого этапа):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_infra.ps1
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_hitk.ps1
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_generation.ps1 -Mode live
```

Только метрики retrieval без generation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_all.ps1 -MilvusOnlyHitk
```

Сценарии PowerShell внутри переходят в корневой каталог проекта и вызывают интерпретатор из `.venv`, если он установлен.

После расширения набора до 300 вопросов для актуализации сводного отчёта выполните полный прогон Hit@k, generation, при необходимости `run_perf_and_judge.ps1`, затем обновите §5.4 в `Readme-4.md` числами из JSON-артефактов.

---

## Краткая схема контура

```
Контрольный вопрос (реестр JSON)
    → эмбеддинг (SentenceTransformer, CUDA/CPU)
    → Milvus, search_text, top-k
    → [Hit@k: сравнение с Clause в чанках]
    → [Generation live: контекст + Ollama → ответ и метрики citation/groundedness/relevance]
    → артефакты в scripts/stage4_eval/results/
```
