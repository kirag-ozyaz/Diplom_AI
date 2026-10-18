# Пошаговый запуск проекта

Единая инструкция: от установки окружения до поиска по базе и (опционально) Telegram-бота.

Ниже два уровня нумерации:

- **Шаги 0–9** — порядок команд в этой инструкции (окружение, Docker, скрипты).
- **Этапы диплома 1–4** — что сдавать в `Этапы/Reports/`; каждый этап = цепочка шагов из этой же инструкции.

> **Краткий путь** (чанки уже есть, Milvus запущен): **0 → 1 → 2 → 4 → 5 → 6 → 7** (этапы **3–4** без пересборки данных).  
> **Полный путь** (с нуля): **0–9** (включая этапы **1–2** в шаге 3).

---

## Этапы диплома (1–4): что прогонять

Перед любым этапом один раз: **шаги 0–2** (venv, `requirements.txt`, `config/rag_runtime.json`).

| Этап | Задача | Прогон (команды) | Отчёт / артефакт |
|------|--------|------------------|------------------|
| **1** | DOCX → Markdown | **Шаг 3.2** — `Create_mds/generator.py -r` | `Этапы/Reports/etap1/Readme-1.md` |
| **2** | Markdown → чанки JSONL | **Шаг 3.3** — `Create_chunkeds/generator.py -r` | `Этапы/Reports/etap2/Readme-2.md` |
| **3** | Чанки → Milvus (эмбеддинги) | **Шаги 4 → 5 → 6** — Milvus, `test_connection.py`, `load_data.py`; для сдачи — ноутбук | `Этапы/Reports/etap3/Readme-3 (ver. 4).ipynb` |
| **4** | RAG: поиск + LLM + метрики | **Шаги 4–8** (Milvus, `load_data`, `query` / `query_test`, Ollama) + блок **«Метрики этапа 4»** ниже | `Этапы/Reports/etap4/Readme-4.md`, ноутбук `Readme-4 (ver. 2).ipynb` |

**Этап 4 — типовой порядок метрик** (подробно: `scripts/stage4_eval/README.md`):

1. **Полный прогон одной командой** (infra → Hit@k → generation live → performance + LLM-judge):
   `powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_all.ps1`
2. Только Hit@k: `run_all.ps1 -MilvusOnlyHitk`. Без performance/judge после generation: `run_all.ps1 -SkipPerfJudge`.
3. По шагам вручную: `run_infra.ps1` → `run_hitk.ps1` → `run_generation.ps1 -Mode live` → `run_perf_and_judge.ps1`.
4. Обновить §5.3 в отчёте при необходимости: `python scripts\stage4_eval\reports\update_readme4_eval_docs.py` (после Hit@k).

Исполняемый отчёт этапа 4 — ячейки ноутбука `Readme-4 (ver. 2).ipynb` (те же сервисы и скрипты, что в мануале stage4_eval).

---

## Что где лежит

| Шаг | Документ / скрипт |
|-----|-------------------|
| Milvus (подробно) | `infra/milvus/Readme.md` |
| Ollama LLM (подробно) | `infra/docker/Dockerfile.ollama/README.md` |
| Конфиг RAG | `config/rag_runtime.json` |
| Профили GPU / модели | `config/model_profiles.json` |
| Общее описание проекта | `Readme.md` (корень), дерево каталогов — § «Структура проекта» |
| Тема и ТЗ платформы | `Диплом/` (`тема/`, `ТЗ/`) |
| Отчёты по этапам | `Этапы/Reports/` |
| Отчёт этапа 4 (RAG) | `Этапы/Reports/etap4/Readme-4.md` |
| Вопросы eval этапа 4 | `data/rag_eval_questions/eval_questions.json` |
| Метрики eval этапа 4 | `scripts/stage4_eval/results/` |

---

## Шаг 0. Требования

- **Python** 3.9+ (рекомендуется 3.10–3.11)
- **Docker Desktop** (для Milvus и Ollama)
- **Git**
- **NVIDIA GPU** + драйверы (опционально, но желательно для эмбеддингов и LLM)
- **NVIDIA Container Toolkit** — только если запускаете Ollama в Docker с GPU

Проверка GPU (PowerShell):

```powershell
nvidia-smi
```

---

## Шаг 1. Окружение Python

Из **корня проекта**:

```powershell
cd X:\Учеба_УИИ\Итоговы_Проект

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

> При ошибках с `torch` / CUDA см. [pytorch.org](https://pytorch.org/get-started/locally/) и установите версию под вашу видеокарту.

---

## Шаг 2. Настройка конфига

Отредактируйте `config/rag_runtime.json`. Для типичного запуска на Windows (Python на хосте, Milvus в Docker):

```json
{
  "vector_db": {
    "host": "localhost",
    "port": "19530",
    "collection_name": "diplom_multimodal"
  },
  "paths": {
    "base_data_path": "data",
    "chunked_path": "data/chunked"
  },
  "models": {
    "text_model_name": "intfloat/multilingual-e5-base",
    "clip_model_name": "ViT-B-32",
    "device_text": "cuda",
    "device_clip": "cpu"
  },
  "model_selection": {
    "auto_select_text_model": true
  }
}
```

- **`device_text: "cpu"`** — если нет CUDA или для отладки (медленнее).
- **`auto_select_text_model: true`** — модель эмбеддингов подберётся по GPU (`config/model_profiles.json`).
- Другие сценарии (Docker-сеть, WSL2): см. раздел «Переключение окружения» в `Readme.md`.

### Включение и отключение CUDA

CUDA ускоряет **embedding-модель** (`load_data`, `query`, `query_test`). На Milvus и Ollama этот параметр не влияет.

**Отключить CUDA (работа на CPU):**

В `config/rag_runtime.json`:

```json
"models": {
  "device_text": "cpu",
  "device_clip": "cpu"
}
```

Перезапуск скриптов не требует переиндексации Milvus.

**Включить CUDA:**

1. В конфиге:

```json
"models": {
  "device_text": "cuda",
  "device_clip": "cpu"
}
```

(`device_clip: "cpu"` — CLIP для изображений; на RTX с малым VRAM так экономнее.)

2. Установить PyTorch **с поддержкой CUDA** (если стояла CPU-версия — сначала удалить):

```powershell
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Для новых видеокарт (RTX 5060 Ti и др.) при необходимости:

```powershell
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

3. Проверка:

```powershell
python -c "import torch; print('cuda:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu mode')"
```

Ожидается: `cuda: True` и имя видеокарты.

**Автоматический fallback:** если в конфиге `"device_text": "cuda"`, а PyTorch без CUDA — код (`multimodal_rag.resolve_torch_device`) сам переключится на **cpu** с предупреждением в консоли. RAG продолжит работать, просто медленнее.

> **Важно:** `pip install torch ...` без `uninstall` может оставить старую CPU-сборку (`Requirement already satisfied`) — тогда `cuda.is_available()` останется `False`.

---

## Шаг 3. Предобработка документов (если данных ещё нет)

Пропустите этот шаг, если в `data/chunked/` уже есть `.jsonl` файлы.

### 3.1. Положите исходники

DOCX/PDF — в `data/raw/` (например `data/raw/Нормативная база/ПУЭ/DOCX/`).

### 3.2. Этап 1 — DOCX → Markdown

```powershell
cd src\preprocessing\Create_mds
python generator.py -r
cd ..\..\..\..
```

По умолчанию: вход `data/raw/.../DOCX`, выход `data/extracted/`.

### 3.3. Этап 2 — Markdown → чанки (JSONL)

```powershell
cd src\preprocessing\Create_chunkeds
python generator.py -r
cd ..\..\..\..
```

По умолчанию: вход `data/extracted/`, выход `data/chunked/`.

---

## Шаг 4. Запуск Milvus

```
docker compose ps -a
```

```powershell
cd infra\milvus
docker compose up -d
docker compose ps
cd ..\..
```

Дождитесь статуса **healthy** у `milvus-standalone`. Подробности, Attu UI, перенос на SSD: `infra/milvus/Readme.md`.

**Нормальные сообщения при `docker compose up -d`:**
- `No services to build` — не ошибка: Milvus использует готовые образы (`image:`), сборка не нужна.
- После обновления compose-файла предупреждение про `version` больше не должно появляться.

Ожидаемый результат `docker compose ps`:

| Контейнер | Статус |
|-----------|--------|
| `milvus-etcd` | Up (healthy) |
| `milvus-minio` | Up (healthy) |
| `milvus-standalone` | Up (healthy), порт **19530** |

**Attu (веб-интерфейс, опционально):**

```powershell
cd infra\docker\Dockerfile.attu
.\start-attu.bat
```

Браузер: http://localhost:3000

---

## Шаг 5. Проверка подключения к Milvus

```powershell
python src\preprocessing\Create_embeddings\test_connection.py
```

Ожидается сообщение об успешном подключении и коллекция `diplom_multimodal` в базе **default** (как в Attu: `/databases/default/...`).

> Если раньше скрипт показывал `[]` — он смотрел в пустую базу `test_db`. Актуальная версия проверяет **default**.

---

## Шаг 6. Загрузка эмбеддингов в Milvus

```powershell
python src\preprocessing\Create_embeddings\load_data.py
```

Скрипт:
- читает `config/rag_runtime.json`;
- выбирает embedding-модель (`model_selector.py`);
- создаёт коллекцию и загружает чанки из `data/chunked/`.

Первый запуск может занять **долго** (скачивание модели + индексация).

> **Внимание:** `load_data.drop_existing: true` в конфиге **удаляет** старую коллекцию. Для дозагрузки установите `false`.

---

## Шаг 7. Поиск по базе

**Интерактивный режим:**

```powershell
python src\preprocessing\Create_embeddings\query.py
```

**Быстрый тест** (запрос из `query_test.search_text` в конфиге):

```powershell
python src\preprocessing\Create_embeddings\query_test.py
```

---

## Шаг 8. Ollama — LLM для ответов (опционально)

Нужен для генерации текста ответа (RAG = поиск + LLM). Подробно: `infra/docker/Dockerfile.ollama/README.md`.

**Проверка CUDA и выбор compose (GPU / CPU):**

```powershell
python scripts\infra_start_system\compute_detect.py
python scripts\infra_start_system\compute_detect.py --apply-config
```

При старте **Milvus / Ollama / start_report_docker** конфиг `rag_runtime.json` синхронизируется автоматически (`device_text`, при `auto_select_ollama_model` — `ollama.model`).

**Запуск Ollama** (автовыбор compose и модели LLM):

```powershell
python scripts\infra_start_system\start_ollama.py --pull
```

Ручной вариант:

```powershell
cd infra\docker\Dockerfile.ollama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
cd ..\..\..
```

Если GPU в Docker недоступен — только CPU:

```powershell
cd infra\docker\Dockerfile.ollama
docker compose -f docker-compose.yml up -d
cd ..\..\..
```

Модель из `config/rag_runtime.json` → `ollama.model` (по умолчанию `qwen2.5:3b`):

```powershell
docker exec ollama ollama pull qwen2.5:3b
```

Для **≥8 ГБ VRAM** (модель из темы диплома):

```powershell
docker exec -it ollama ollama pull llama3.1:8b
```

Проверка API:

```powershell
curl http://localhost:11434/api/tags
```

**Проверка Ollama и RAG (из корня проекта):**

```powershell
python scripts\check\test_ollama.py
python scripts\check\test_rag_ollama.py "Что такое нулевой защитный проводник?"
```

Модель LLM задаётся в `config/rag_runtime.json` → секция `ollama` (должна совпадать с `ollama pull`).

---

## Шаг 9. Telegram-бот (заготовка)

RAG в боте **ещё не подключён** — бот отвечает заглушкой. Запуск для проверки каркаса:

```powershell
$env:TG_BOT_TOKEN = "ваш_токен_от_BotFather"
pip install aiogram>=3.0
python -m src.bot
```

---

## Сводная схема

```
data/raw (DOCX)
    → [шаг 3.2] data/extracted (*.md)
    → [шаг 3.3] data/chunked (*.jsonl)
    → [шаг 6]   Milvus (векторная БД)
    → [шаг 7]   query.py / query_test.py
    → [шаг 8+9] Ollama (LLM) + Telegram-бот (в разработке)
```

---

## Частые проблемы

| Симптом | Что проверить |
|---------|----------------|
| `Сервер векторной БД недоступен` | Milvus запущен? `docker compose ps` в `infra/milvus` |
| `host` не подключается из WSL | В конфиге: `"host": "host.docker.internal"` |
| CUDA / out of memory | `"device_text": "cpu"` или легче модель в `model_profiles.json` |
| Пустой поиск | Коллекция создана? `load_data.py` завершился без ошибок? |
| `Torch not compiled with CUDA enabled` | В конфиге `"device_text": "cuda"`, но PyTorch **CPU-only**. Скрипт теперь сам переключится на cpu; для GPU: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124` |
| `query_test.py` / `query.py` «висит» без вывода | Первый запуск: загрузка torch и embedding-модели (1–3 мин). |

---

## Метрики этапа 4 (Hit@k + generation)

См. таблицу **«Этапы диплома (1–4)»** в начале файла. Пошаговый мануал и PowerShell-обёртки: **`scripts/stage4_eval/README.md`**.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage4_eval\run_all.ps1
```

---

## Полезные команды (шпаргалка)

```powershell
# Milvus — остановить
cd infra\milvus; docker compose down; cd ..\..

# Milvus — полный сброс БД (удалит данные!)
cd infra\milvus; docker compose down -v; docker compose up -d; cd ..\..

# Ollama — логи
docker logs -f ollama

# Обновить каталог embedding-моделей
python scripts\infra_start_system\update_model_profiles.py
```
