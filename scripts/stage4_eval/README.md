# Этап 4 — сбор метрик качества RAG (Hit@k и generation)

Данный каталог объединяет скрипты **оценки** прототипа RAG по Правилам устройства электроустановок (ПУЭ): измерение качества **поиска фрагментов** (метрики Hit@1, Hit@3, Hit@5) и качества **генерации ответа** языковой моделью (цитирование нормы, опора на контекст, релевантность). Скрипты запуска контейнеров Docker (Milvus, Ollama) расположены на уровень выше — в каталоге `scripts/`.

Все команды ниже выполняются **из корня репозитория**. Рекомендуется активировать виртуальное окружение:

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

**Дополнительные материалы проекта:**

- теория метрики Hit@k — `manual/Hit_at_k.md`;
- текст отчёта этапа 4 — `Этапы/Reports/etap4/Readme-4.md`;
- исполняемый ноутбук — `Этапы/Reports/etap4/Readme-4 (ver. 2).ipynb`;
- единые пути к артефактам в коде — `scripts/report_paths.py`;
- пояснение к прогону generation — `Этапы/Reports/etap4/generation/Etap4-gen-metrics.md`.

---

## Зачем выполняется сбор метрик

На четвёртом этапе дипломного проекта требуется показать **рабочий контур RAG** и **первую количественную оценку** его компонентов.

**Retrieval (Hit@k).** Для каждого тестового вопроса выполняется один семантический поиск в Milvus. Успех для Hit@k означает, что среди первых *k* найденных фрагментов в тексте чанка встречается номер эталонного пункта ПУЭ (`Clause`), заданный в файле вопросов. Языковая модель Ollama в этом прогоне **не используется**: оценивается только этап поиска.

**Generation.** После retrieval (или в режиме имитации без Docker) формируется ответ модели по найденному контексту. Скрипт `eval_rag_generation.py` считает долю ответов с корректным цитированием, среднюю «заземлённость» ответа на контекст (groundedness) и релевантность эталонному пункту. Для осмысленной live-оценки должны быть доступны и Milvus (порт 19530), и Ollama (порт 11434).

**Результаты** сохраняются в `Этапы/Reports/etap4/` (подкаталоги `retrieval/` и `generation/`) и используются в отчёте Word, в markdown и в ноутбуке.

Тестовые вопросы и эталонные пункты: `Этапы/Reports/etap4/data/stage4_eval_questions.json`. Формулировки вопросов можно готовить по билетам электробезопасности (см. `manual/tests24_electro_safety.md`, данные в `data/tests24/`).

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

Отдельно `python scripts/start_milvus.py` и ручная цепочка Python нужны только если вы **не** используете PowerShell-сценарии. Если generation оборвался на середине (в JSON есть `error`, Milvus «упал»), но `run_all` уже завершился с кодом 0 — снимок логов вручную: `python scripts/start_milvus_logs.py` (см. `infra/milvus/Storage.md`).

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

- создаются или обновляются `stage4_hitk_results.json`, `stage4_hitk_chart.png`, `stage4_hitk_report.png` в `Этапы/Reports/etap4/retrieval/`;
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
| Тестовые вопросы и эталоны Clause | `Этапы/Reports/etap4/data/stage4_eval_questions.json` |
| Последний прогон Hit@k (JSON) | `Этапы/Reports/etap4/retrieval/stage4_hitk_results.json` |
| История всех прогонов Hit@k | `Этапы/Reports/etap4/retrieval/stage4_hitk_runs.jsonl` |
| Столбчатая диаграмма Hit@k | `Этапы/Reports/etap4/retrieval/stage4_hitk_chart.png` |
| Сводный график для Word | `Этапы/Reports/etap4/retrieval/stage4_hitk_report.png` |
| Метрики generation | `Этапы/Reports/etap4/generation/stage4_gen_eval_results.json` |
| Текстовое пояснение к generation | `Этапы/Reports/etap4/generation/Etap4-gen-metrics.md` |

В файле generation имеет смысл проверить поля `mode_effective`, `blockers`, `metrics.n_questions` и `metrics.partial_run` (при значении `true` обработаны не все вопросы набора).

---

## Связанные скрипты в каталоге `scripts/`

| Скрипт | Назначение |
|--------|------------|
| `report_paths.py` | Константы путей к артефактам этапа 4 |
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

### Способ 1 — команды Python (из корня репозитория)

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

Сценарии PowerShell внутри переходят в корень репозитория и вызывают интерпретатор из `.venv`, если он установлен.

---

## Краткая схема контура

```
Тестовый вопрос (JSON)
    → эмбеддинг (SentenceTransformer, CUDA/CPU)
    → Milvus, search_text, top-k
    → [Hit@k: сравнение с Clause в чанках]
    → [Generation live: контекст + Ollama → ответ и метрики citation/groundedness/relevance]
    → артефакты в Этапы/Reports/etap4/
```
