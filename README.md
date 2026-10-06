=============================================================== 28.01.2026 23:36
Тема итогового проекта
"Разработка интеллектуального Telegram-бота на основе языковой модели для консультирования по нормативной документации в области электроэнергетики (ПУЭ, ПТЭЭП, ГОСТ)"
1. Предпосылки (почему выбрали именно эту тему?)
  Работая в энергетической отрасли, я ежедневно сталкиваюсь с ситуацией, когда инженерам, электромонтажникам и другим специалистам требуется оперативно найти ответ в нормативных документах — ПУЭ, ПТЭЭП и прочей нормативной документации по электроэнергетике
2. Описание задачи.
  Разработать интеллектуального Telegram-бота, способного:
  - Принимать вопросы пользователя на естественном русском языке по вопросам проектирования, монтажа и эксплуатации электроустановок;
  - Осуществлять семантический поиск пунктов нормативных документов (ПУЭ, ПТЭЭП, прочая нормативная документация по электроэнергетике);
  - Формировать структурированные ответы с точными ссылками на пункты, таблицы и рисунки документов;
3. Как видите ее решение
  База знаний — структурированные тексты ПУЭ, ПТЭЭП и ГОСТ с метаданными (раздел, пункт, статус требования: «обязательно» / «рекомендуется»).
  Векторное хранилище — локальная база для хранения эмбеддингов фрагментов документов.
  Языковая модель — для генерации ответов основной вариант: GigaChat, может быть развёрнута локальную бесплатную альтернативу модель Llama 3.1 8B через Ollama.
  Бот-платформа — асинхронный фреймворк Telegram Bot API.
  Хранение диалога — локальная СУБД SQLite для сохранения истории сообщений (возможна замена на Redis при необходимости повышения производительности).
4. Какую базу планируете использовать
   Предварительно - это Нормативная база электроэнергетики:
   - Правила устройства электроустановок 7-го издания (ПУЭ)
   - Правила технической эксплуатации электроустановок потребителей электрической энергии (ПТЭЭП)
   - прочая нормативная документация по электроэнергетике
=============================================================== 29.01.2026 16:30
=================== Ответ Куратора ============================
Куратор Анастасия Вишногорская (DS, GPT)
29 January 2026 (Thursday), 15:30
Добрый день, Александр! Тема утверждается при условии, что вы учтёте риски и сузите фокус на первом этапе.

Ключевые риски и моменты, требующие уточнения:

1. Объём данных и их подготовка: «Предварительно — это Нормативная база...» — это потенциально огромный объём неструктурированного текста (сотни страниц PDF). Самый трудоёмкий этап здесь — не написание бота, а предобработка документов: извлечение текста из PDF, разбиение на смысловые фрагменты (глава/пункт/подпункт), очистка, создание структуры с метаданными. На это может уйти 60-70% времени. Рекомендация: Начните с одного документа (например, ПУЭ, Раздел 1). Это позволит быстро отладить весь пайплайн.
2. Выбор языковой модели:
  - GigaChat/YandexGPT: Удобный API, но создаёт зависимость от внешнего сервиса, требует API-ключ и может нести затраты. Также есть вопрос о приватности запросов.
  - Локальная Llama 3.1 8B через Ollama: Полная независимость и приватность, но требует хорошего CPU/GPU (минимум 16 ГБ ОЗУ, лучше — GPU с 8+ ГБ памяти). Проверьте на своём железе, потянет ли она инференс с приемлемой скоростью. Для поиска и ответа по документам можно рассмотреть более лёгкие модели (например, Phi-3 mini, Mistral 7B).
3. Архитектура «сэндвича» (RAG — Retrieval-Augmented Generation): Вы её правильно описали: векторный поиск → LLM для генерации ответа. Это современный и адекватный подход. Нужно будет настроить чункер (разбиение текста) и метрику похожести для поиска.
Итог и рекомендации перед стартом:

 

Конкретные рекомендации:

1. Сузьте MVP: Чётко определить, что входит в первую версию. Например: *«Telegram-бот, работающий с Разделом 1 и Разделом 6 ПУЭ, на основе локально развёрнутой модели Llama 3.1 8B (или Phi-3)».*
2. Детализируйте план предобработки данных: Описать, как именно будут извлекаться и структурироваться данные из PDF (библиотеки: pymupdf, pdfplumber), как будут создаваться эмбеддинги (модель: sentence-transformers/all-MiniLM-L6-v2).
3. Протестируйте инференс модели: Убедиться, что выбранная LLM (особенно локальная) может стабильно генерировать связные ответы на тестовых примерах с предоставленным контекстом.

Резюме: Тема отличная, так как решает реальную проблему, имеет чёткие границы и позволяет продемонстрировать полный цикл работы с современным ML-стеком (векторные БД, RAG, LLM, боты). Главное — не утонуть в данных на старте и выбрать работоспособную модель.
==============================================================================
Учебник по Markdown
https://www.markdownlang.com/ru/advanced/math.html
https://markdown.com.cn/
https://marketplace.visualstudio.com/items?itemName=goessner.mdmath

Markdown+Math

https://code.visualstudio.com/docs/languages/python
==============================================================================
Архитектура системы:
```
┌─────────────────────────────────────────────────────────────────────┐
│                      ПАЙПЛАЙН ОБРАБОТКИ ДОКУМЕНТОВ                   │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│  Исходники   │  ←  ./raw/
│ (PDF/DOCX)   │      • ПУЭ_7е_издание.pdf
└──────┬───────┘      • ПТЭЭП_2023.docx
       │
       ▼  [pdfplumber, python-docx, pandoc]
       │     └─► извлечение текста + форматирование в Markdown
       │
┌──────────────┐
│  extracted/  │  ←  ./extracted/
│   (*.md)     │      • pue_section_1.md
└──────┬───────┘      • pue_section_6.md
       │              • pteep_general.md
       ▼  [сегментация с метаданными]
       │     └─► разбивка по §/п. + извлечение:
       │          • номер раздела/главы/пункта
       │          • статус (обязательно/рекомендуется)
       │          • заголовок пункта
       │
┌──────────────┐
│  chunked/    │  ←  ./chunked/
│  (JSON/CSV)  │      [
└──────┬───────┘        {
       │                  "id": "pue_1.1.1",
       │                  "text": "Электроустановки...",
       │                  "section": "1.1",
       │                  "clause": "1.1.1",
       │                  "status": "mandatory",
       │                  "source_file": "pue_section_1.md"
       │                },
       │                ...
       │              ]
       ▼  [sentence-transformers / multilingual-e5-base / bge-m3 — автовыбор по GPU]
       │
┌──────────────┐
│ embeddings/  │  ←  ./embeddings/
│ (Chroma DB)  │      • chroma.sqlite3, Milvus, Qdrant
└──────┬───────┘      • index/
       │
       ▼  [RAG-запрос]
┌──────────────┐
│ Telegram-бот │  ←  Поиск → Релевантные чанки → LLM (qwen2.5:3b / llama3.2:3b / llama3.1:8b)
│  (Ollama)    │      → Структурированный ответ с ссылками на ПУЭ/ПТЭЭП
│              │      Конфиг: config/rag_runtime.json + model_profiles.json
└──────────────┘
```

## Структура проекта

```
energy_norms_bot/
├── infra/                              # Инфраструктура и развертывание
│   ├── docker/                         # Docker-конфигурации (в разработке)
│   │   ├── Dockerfile.bot/             # Docker для Telegram-бота
│   │   │   ├── Dockerfile
│   │   │   └── docker-compose.yml
│   │   ├── Dockerfile.preprocessing    # Dockerfile для скриптов обработки
│   │   ├── Dockerfile.ollama/          # Ollama в Docker (LLM для RAG-бота)
│   │   │   ├── README.md               # Подробная инструкция: запуск, модели, API
│   │   │   └── docker-compose.yml      # Compose для Ollama с поддержкой NVIDIA GPU
│   │   ├── docker-compose.yml          # Основной compose для всех сервисов
│   │   └── .env.example                # Пример переменных окружения
│   ├── Docker.attu/                    # Docker для Attu UI
│   │   ├── start-attu.bat              # Скрипт запуска Attu UI (Windows)
│   │   └── start-attu.sh               # Скрипт запуска Attu UI (Linux/Mac)
│   ├── milvus/
│   │   ├── docker-compose.yml          # Compose для Milvus (etcd, minio, standalone)
│   │   ├── .env                        # Переменные окружения (не в git)
│   │   ├── .env.example                # Пример переменных окружения. Путь к томам (для SSD: DOCKER_VOLUME_DIRECTORY)
│   │   └── Readme.md                   # Запуск, Attu, перенос на SSD, пересборка БД
│   ├── ollama/                         # См. infra/docker/Dockerfile.ollama/
│   └── info.md                         # Общая информация по инфраструктуре
├── src/                                # Исходный код приложения
│   ├── bot/                            # Telegram-бот (aiogram, RAG в разработке)
│   │   └── __main__.py                 # Запуск: python -m src.bot (TG_BOT_TOKEN)
│   ├── preprocessing/                  # Модули предобработки документов
│   │   ├── Create_mds/                 # Этап 1: DOCX → Markdown
│   │   │   ├── docx_to_md_images_1.py  # Конвертация DOCX → Markdown с изображениями
│   │   │   └── generator.py            # Массовая обработка документов
│   │   ├── Create_chunkeds/            # Этап 2: Markdown → Chunks
│   │   │   ├── md_to_chunked_2.py      # Сегментация Markdown → JSONL chunks
│   │   │   ├── generator.py            # Массовая обработка чанков
│   │   │   └── pipeline_create_chunked.md  # Документация пайплайна
│   │   ├── Create_embeddings/          # Этап 3: Chunks → Векторная БД
│   │   │   ├── multimodal_rag.py       # Класс MultimodalRAG для работы с Milvus
│   │   │   ├── load_data.py            # Загрузка данных в векторную БД
│   │   │   ├── query.py                # Интерактивный поиск по базе
│   │   │   ├── query_test.py           # Тестовый поиск
│   │   │   ├── test_connection.py      # Проверка подключения к Milvus
│   │   │   ├── runtime_config.py       # Загрузка config/rag_runtime.json
│   │   │   ├── model_selector.py       # Автовыбор embedding-модели по GPU
│   │   │   └── embedding_config.json   # Конфигурация моделей эмбеддингов (dim, default)
│   │   ├── __init__.py
│   │   └── main.py                     # Главный скрипт запуска пайплайна
│   ├── rag/                            # RAG-модуль (в разработке)
│   └── __init__.py
├── data/                               # Данные проекта
│   ├── raw/                            # Исходные документы (PDF/DOCX)
│   │   ├── База исходники/
│   │   └── Нормативная база/
│   ├── extracted/                      # Извлеченный текст в Markdown (*.md + image_*/)
│   ├── chunked/                        # Сегментированные данные (*.jsonl + image_*/)
│   └── embeddings/                     # Векторная база данных Milvus
├── config/                             # Runtime-конфигурация RAG и профили моделей
│   ├── rag_runtime.json                # Хост Milvus, пути, устройства, load_data/query
│   └── model_profiles.json             # Профили GPU, overrides, каталог кандидатов моделей
├── scripts/
│   └── update_model_profiles.py        # Обновление candidates в model_profiles.json (HF + Ollama)
├── start/
│   └── Readme.md                       # ★ Пошаговый запуск проекта (с нуля до query/бота)
├── Этапы/
│   └── Reports/                        # Отчеты по этапам проекта
│       ├── Readme-1.md                 # Отчет: Этап 1 (DOCX → MD)
│       ├── Readme-2.md                 # Отчет: Этап 2 (MD → Chunks)
│       ├── Readme-3.md                 # Отчет: Этап 3 (Chunks → Embeddings)
│       └── Readme-3.ipynb              # Jupyter notebook для Этапа 3
├── Информация/                         # Справочные материалы
├── Тема/                               # Материалы по теме проекта
├── .gitignore
└── Readme.md                           # Описание проекта (этот файл)
```

---

## Пошаговый запуск

**Полная инструкция:** [`start/Readme.md`](start/Readme.md) — установка, конфиг, Milvus, загрузка данных, поиск, Ollama, бот.

Кратко (если `data/chunked/` уже готов):

```powershell
# 0. Окружение (один раз)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1. Milvus
cd infra\milvus; docker compose up -d; cd ..\..

# 2. Загрузка + поиск
python src\preprocessing\Create_embeddings\load_data.py
python src\preprocessing\Create_embeddings\query_test.py
```

---

## Ollama в Docker (LLM для RAG-бота)

Локальный запуск языковой модели через Ollama в Docker для работы Telegram-бота с RAG.

**Расположение:** `infra/docker/Dockerfile.ollama/`

**Быстрый старт:**
```bash
cd infra/docker/Dockerfile.ollama
docker compose up -d
```

**Требования:** NVIDIA GPU (RTX 2060 и выше), NVIDIA Container Toolkit, 16+ ГБ ОЗУ.

**API:** `http://localhost:11434` (с хоста) или `http://ollama:11434` (из Docker Compose).

**Рекомендуемые модели для RTX 2060 (6 ГБ VRAM):**
- `qwen2.5:3b` — лучшая для русского языка и технических текстов (ПУЭ, ПТЭЭП)
- `llama3.2:3b` — универсальная
- `phi3:mini` — для работы с нормативами и документацией

**Рекомендуемые модели для ≥8–12 ГБ VRAM (квантование Q4):**
- `llama3.1:8b` — изначально запланированная модель проекта (~4.7 GB, Q4)
- `llama3.1:8b-instruct-q4_K_M` — instruct-версия с явным Q4_K_M для RAG-промптов
- `qwen2.5:7b` — альтернатива с сильным русским языком (7B-класс)
- `mistral:7b` — баланс качества и скорости на 8 ГБ VRAM

> На RTX 2060 (6 ГБ) Llama 3.1 8B **не рекомендуется** — используйте 3B-модели из первого списка или GPU с ≥8 ГБ VRAM.

Подробная инструкция (модели, команды, примеры кода, промпты для ПУЭ): см. `infra/docker/Dockerfile.ollama/README.md`.

---

## Переключение окружения только через конфиг

Все runtime-параметры RAG вынесены в `config/rag_runtime.json`:
- `vector_db.host/port/collection_name` — подключение к Milvus
- `paths.base_data_path`, `paths.chunked_path` — пути к данным
- `models.device_text/device_clip`, `models.text_model_name` — устройства и модель эмбеддингов
- `model_selection.auto_select_text_model` — автовыбор модели по GPU
- `load_data.*` — параметры загрузки (`drop_existing`, `use_async`, `batch_size`, …)
- `query.default_limit` — лимит результатов в интерактивном поиске
- `query_test.search_text/limit` — тестовый запрос для `query_test.py`

Профили авто-выбора модели по GPU лежат в `config/model_profiles.json`:
- `profiles` — набор профилей по VRAM (`rtx2060_baseline`, `mid_gpu`, `high_gpu`)
- `gpu_name_overrides` — привязка конкретной видеокарты к профилю (например, RTX 2060 → `all-MiniLM-L6-v2`)
- `candidates` — каталог embedding/LLM-моделей (обновляется скриптом `scripts/update_model_profiles.py`)

**Автовыбор embedding-модели** (`model_selector.py`):
1. `auto_select_text_model=false` → берётся `models.text_model_name`
2. override по имени GPU из `gpu_name_overrides`
3. match по VRAM из `profiles`
4. `default_profile` из `model_profiles.json`
5. fallback на `models.text_model_name`

**Обновление каталога моделей:**
```bash
python scripts/update_model_profiles.py
# или с лимитами:
python scripts/update_model_profiles.py --max-hf-per-query 5 --max-ollama-models 20
```
Скрипт дополняет `candidates` моделями из Hugging Face API, Ollama и `embedding_config.json`, не удаляя закреплённые (`pinned`) записи.

### Включение и отключение CUDA (embedding)

Параметры в `config/rag_runtime.json` → секция `models`:

| Режим | `device_text` | `device_clip` | Когда |
|-------|---------------|---------------|--------|
| **CPU** | `"cpu"` | `"cpu"` | Нет GPU, отладка, PyTorch без CUDA |
| **GPU** | `"cuda"` | `"cpu"` | Есть NVIDIA + PyTorch с CUDA |

**Отключить:** `"device_text": "cpu"` — достаточно для работы на процессоре.

**Включить:**
1. `"device_text": "cuda"` в конфиге.
2. PyTorch с CUDA (из venv, после удаления CPU-сборки):

```powershell
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(torch.cuda.is_available())"
```

Если `False` после установки — переустановите с `cu128` или проверьте драйвер NVIDIA (`nvidia-smi`).

При `"cuda"` в конфиге, но CPU-only PyTorch — **авто-fallback на cpu** (`multimodal_rag.py`), ошибки не будет.

Подробнее: [`start/Readme.md`](start/Readme.md) → шаг 2.

### Пример 1: local (Python на хосте, Milvus на localhost)

```json
{
  "vector_db": { "host": "localhost", "port": "19530", "collection_name": "diplom_multimodal" },
  "paths": { "base_data_path": "data", "chunked_path": "data/chunked" },
  "models": { "device_text": "cuda", "device_clip": "cpu", "text_model_name": "intfloat/multilingual-e5-base" },
  "model_selection": { "auto_select_text_model": true }
}
```

### Пример 2: Docker Compose (скрипт внутри одной сети с Milvus)

```json
{
  "vector_db": { "host": "milvus-standalone", "port": "19530", "collection_name": "diplom_multimodal" },
  "paths": { "base_data_path": "data", "chunked_path": "data/chunked" },
  "models": { "device_text": "cuda", "device_clip": "cpu", "text_model_name": "intfloat/multilingual-e5-base" },
  "model_selection": { "auto_select_text_model": true }
}
```

### Пример 3: WSL2/Linux (Docker на Windows, доступ с WSL к хосту)

```json
{
  "vector_db": { "host": "host.docker.internal", "port": "19530", "collection_name": "diplom_multimodal" },
  "paths": { "base_data_path": "data", "chunked_path": "data/chunked" },
  "models": { "device_text": "cuda", "device_clip": "cpu", "text_model_name": "intfloat/multilingual-e5-base" },
  "model_selection": { "auto_select_text_model": true }
}
```

Если нужно зафиксировать модель вручную, отключите авто-выбор:

```json
"model_selection": { "auto_select_text_model": false }
```

Тогда будет использована модель из `models.text_model_name`.

**Профили GPU по умолчанию** (`config/model_profiles.json`):

| Профиль | VRAM | Модель эмбеддингов |
|---------|------|--------------------|
| `rtx2060_baseline` | ≤ 8 ГБ | `sentence-transformers/all-MiniLM-L6-v2` |
| `mid_gpu` | 8–12 ГБ | `intfloat/multilingual-e5-base` |
| `high_gpu` | ≥ 12 ГБ | `BAAI/bge-m3` |

### Быстрый запуск RAG-скриптов

> Подробнее (все шаги с нуля): **[start/Readme.md](start/Readme.md)**

Все скрипты читают `config/rag_runtime.json` — менять код не нужно, достаточно отредактировать конфиг.

```bash
# 1. Запустить Milvus (см. infra/milvus/Readme.md)
cd infra/milvus && docker compose up -d

# 2. Загрузить чанки в векторную БД
python src/preprocessing/Create_embeddings/load_data.py

# 3. Интерактивный поиск
python src/preprocessing/Create_embeddings/query.py

# 4. Быстрый тест (запрос из query_test.search_text в конфиге)
python src/preprocessing/Create_embeddings/query_test.py
```

**Telegram-бот** (заготовка, RAG ещё не подключён):
```bash
set TG_BOT_TOKEN=your_token   # Windows
python -m src.bot
```

---

## Виртуальная карта кода приложения

Карта классов, методов, функций и связей между модулями проекта.

### Обзор модулей

| Модуль | Назначение |
|--------|------------|
| `src/preprocessing/Create_mds/` | Конвертация DOCX → Markdown с изображениями |
| `src/preprocessing/Create_chunkeds/` | Сегментация Markdown → чанки (JSONL) с метаданными ПУЭ |
| `src/preprocessing/Create_embeddings/` | Multimodal RAG: эмбеддинги, Milvus, поиск; runtime-конфиг и автовыбор модели |
| `config/` | `rag_runtime.json` — параметры окружения; `model_profiles.json` — профили GPU |
| `scripts/update_model_profiles.py` | Обновление каталога embedding/LLM-моделей в `model_profiles.json` |

---

### 1. Create_mds (DOCX → Markdown)

**Файлы:** `docx_to_md_images_1.py`, `generator.py`

#### docx_to_md_images_1.py — функции (без классов)

| Функция | Описание |
|---------|----------|
| `clean_hidden_tags_in_docx(docx_path)` | Удаляет скрытые метки (#G0, #M..., #S и т.п.) из параграфов и ячеек таблиц DOCX. Возвращает `Document`. |
| `clean_hidden_tags_in_markdown(markdown_content)` | Удаляет те же скрытые метки из уже сгенерированного Markdown-текста. |
| `merge_split_headers(markdown_content)` | Объединяет заголовки, разбитые на несколько строк, в одну строку. |
| `extract_images_and_fix_refs(docx_path, output_dir, file_stem)` | Извлекает изображения из DOCX во внешние файлы и строит карту путей для подстановки в HTML/MD. |
| `replace_image_tags_in_html(html, image_map, images_folder_name, images_dir)` | Заменяет ссылки на изображения в HTML на актуальные пути. |
| `fix_images_in_markdown(markdown_content, images_dir, images_folder_name)` | Исправляет ссылки на изображения в Markdown под заданную папку. |
| `docx_to_md_with_images(docx_path, output_dir=None, merge_headers=False)` | **Точка входа:** конвертирует один DOCX в Markdown с извлечёнными изображениями; возвращает строку MD. |

#### generator.py (Create_mds)

| Элемент | Тип | Описание |
|--------|-----|----------|
| `convert_file(docx_path, input_dir, output_dir, semaphore)` | async-функция | Конвертирует один DOCX в MD через `docx_to_md_with_images` (передаёт `output_dir`), сохраняет структуру каталогов. |
| `main()` | async-функция | Парсит аргументы (-i, -o, -j, -r), по умолчанию использует `data/raw/.../DOCX` и `data/extracted`; находит все .docx, запускает `convert_file` с семафором. |
| Зависимость | импорт | `from docx_to_md_images_1 import docx_to_md_with_images` |

---

### 2. Create_chunkeds (Markdown → Chunked JSONL)

**Файлы:** `md_to_chunked_2.py`, `generator.py`

#### md_to_chunked_2.py

**Класс: `PueMetadataParser`**

| Метод | Описание |
|-------|----------|
| `__init__(self)` | Инициализирует `metadata` (Document, Section, Chapter, Paragraph, Clause) и флаг `is_header_line`. |
| `parse_line(self, line: str) -> dict \| None` | Парсит одну строку MD; возвращает словарь с метаданными и полем `Content`, или `None`. Распознаёт: ### Document, ## Раздел, # Глава, # Paragraph, (X.Y.Z) Clause, контент. |
| `_reset(self, keys: list)` | Обнуляет указанные ключи в `metadata`. |
| `_make_record(self, content: str) -> dict` | Возвращает копию метаданных + `Content` и `_is_header`. |

**Функции (вне класса):**

| Функция | Описание |
|---------|----------|
| `chunk_document(content, source_file)` | Разбивает контент на чанки с помощью `PueMetadataParser`; возвращает список чанков. |
| `create_chunk_obj(metadata_record, content_lines, source_file)` | Формирует объект чанка (id, text, section, chapter, paragraph, clause, source_file и т.д.) для записи в JSONL. |
| `copy_images_from_markdown(md_path, output_dir, content)` | Копирует изображения, на которые ссылается MD, в выходную директорию с сохранением структуры. |
| `generate_chunked_file(md_path, output_dir)` | **Точка входа:** читает MD, вызывает `chunk_document` и `create_chunk_obj`, записывает JSONL и копирует изображения. |

#### generator.py (Create_chunkeds)

| Элемент | Тип | Описание |
|--------|-----|----------|
| `convert_file(md_path, input_dir, output_dir, semaphore)` | async-функция | Конвертирует один MD в chunked JSONL через `generate_chunked_file`. |
| `main()` | async-функция | Аргументы -i, -o, -j, -r; по умолчанию `data/extracted` и `data/chunked`; поиск .md; параллельный запуск `convert_file`. |
| Зависимость | импорт | `from md_to_chunked_2 import generate_chunked_file` |

---

### 3. Create_embeddings (Multimodal RAG)

**Файлы:** `multimodal_rag.py`, `load_data.py`, `query.py`, `query_test.py`, `test_connection.py`, `runtime_config.py`, `model_selector.py`, `embedding_config.json`

#### embedding_config.json

| Назначение | Описание |
|------------|----------|
| Конфиг эмбеддингов | Словарь `text_model_dim` (модель → размерность), `default_text_model`, `default_dim`. Используется для подстановки `text_dim` при инициализации RAG и в `get_default_embedding_model()` при отсутствии метаданных коллекции. Дополняет `model_profiles.json` локальными dim-значениями. |

#### runtime_config.py

| Функция / константа | Описание |
|---------------------|----------|
| `ROOT` | Корень репозитория (3 уровня выше модуля). |
| `DEFAULT_CONFIG_PATH` | Путь к `config/rag_runtime.json`. |
| `DEFAULT_RUNTIME_CONFIG` | Встроенные значения по умолчанию (Milvus, пути, модели, load_data, query). |
| `load_runtime_config(config_path=None)` | Загружает и мержит JSON-конфиг с дефолтами; при ошибке/отсутствии файла — безопасный fallback. |
| `resolve_repo_path(path_value)` | Преобразует относительный путь из конфига в абсолютный от корня репозитория. |

#### model_selector.py

| Функция / класс | Описание |
|-----------------|----------|
| `GpuInfo` | dataclass: `name`, `vram_gb`, `source` (nvidia-smi или torch.cuda). |
| `detect_gpu_info()` | Определяет GPU через `nvidia-smi`, затем через `torch.cuda`. |
| `select_text_model(runtime_cfg)` | **Точка входа:** возвращает `(model_name, reason)` — выбор embedding-модели по конфигу и GPU. |
| `_load_model_profiles()` | Читает `config/model_profiles.json`. |
| `_match_profile_by_vram()` | Подбирает профиль по диапазону VRAM. |

#### multimodal_rag.py — функции модуля (вне класса)

| Функция | Тип | Описание |
|---------|-----|----------|
| `_load_embedding_config()` | — | Читает `embedding_config.json`; возвращает dict или None при ошибке/отсутствии файла. |
| `_get_text_dim_from_config(text_model_name)` | — | Возвращает `text_dim` для модели из конфига; при отсутствии — `default_dim` или 384. |
| `get_default_embedding_model()` | — | Возвращает `(default_text_model, text_dim)` из конфига. Используется в query/query_test при недоступных метаданных коллекции. |

#### multimodal_rag.py — класс `MultimodalRAG`

**Инициализация и подключение**

| Метод | Тип | Описание |
|-------|-----|----------|
| `__init__(...)` | конструктор | Параметры: vector_db_host/port, collection_name, text_model_name, clip_model_name, device_text/clip, base_data_path, image_encode_workers, batch_chunk_workers, load_image_model, text_dim (опционально — при None берётся из `embedding_config.json` по text_model_name). Вызывает `_connect_vector_db`, `_load_text_model`, при необходимости `_load_clip_model`. |
| `_check_vector_db_available(host, port, timeout)` | @staticmethod | Проверяет доступность векторной БД по сокету; используется внутренне. |
| `check_vector_db_server(host, port, timeout)` | @staticmethod | Публичная проверка доступности векторной БД (port — строка или число). Для скриптов query, query_test и т.д. Возвращает bool. |
| `_connect_vector_db(self)` | private | Проверяет доступность через `_check_vector_db_available`, подключается к векторной БД по host:port; при недоступности — выход из процесса. |
| `_load_text_model(self, model_name, device)` | private | Загрузка SentenceTransformer для текстовых эмбеддингов. |
| `_load_clip_model(self, model_name, device)` | private | Загрузка CLIP (open_clip) для эмбеддингов изображений. |

**Коллекция и индексы**

| Метод | Описание |
|-------|----------|
| `create_collection(self, drop_existing=True)` | Создаёт коллекцию в векторной БД (поля: id, chunk_id, text_vector, image_vector, text, image_paths, source_file, chapter, has_image), индексы HNSW для text_vector и image_vector. |
| `load_collection(self)` | Загружает коллекцию в память для поиска; проверяет совпадение text_model/text_dim с метаданными. |

**Метаданные эмбеддингов**

| Метод | Тип | Описание |
|-------|-----|----------|
| `_parse_embedding_meta(description)` | @staticmethod | Извлекает из строки описания коллекции (description) `text_model` и `text_dim` по regex; возвращает dict или None. |
| `get_collection_embedding_meta(self)` | instance | Возвращает метаданные эмбеддингов текущей коллекции. |
| `get_embedding_meta_from_collection(cls, vector_db_host, vector_db_port, collection_name)` | @classmethod | Подключается к векторной БД и читает метаданные коллекции без создания экземпляра RAG. |

**Извлечение и кодирование**

| Метод | Описание |
|-------|----------|
| `_extract_images_from_chunk(self, chunk_text, chapter, base_dir)` | Извлекает пути к изображениям из текста чанка (Markdown/HTML-ссылки), резолвит относительно base_dir. |
| `_encode_text(self, texts)` | Векторизация списка текстов (SentenceTransformer, normalize_embeddings=True). |
| `_encode_image(self, image_path)` | Векторизация одного изображения через CLIP; при ошибке — нулевой вектор. |
| `_encode_images_batch(self, image_paths)` | Векторизация нескольких изображений (с потоками); возвращает один усреднённый вектор на чанк. |

**Загрузка данных**

| Метод | Описание |
|-------|----------|
| `load_from_jsonl_folder(self, jsonl_folder, batch_size, skip_existing, ...)` | Синхронная загрузка: читает JSONL из папки, кодирует текст и изображения, вставляет батчи в векторную БД. |
| `load_from_jsonl_folder_async(self, jsonl_folder, batch_size, ...)` | Асинхронный вариант загрузки (insert/flush в потоках), с прогрессом и сводкой по файлам. |

**Поиск**

| Метод | Описание |
|-------|----------|
| `search_text(self, query, limit=5, filter_chapter=None, with_images_only=False)` | Поиск по текстовому запросу; возвращает список dict (id, score, chunk_id, text, image_paths, source_file, chapter, has_image, search_type). |
| `search_image(self, image_path, limit=5, filter_chapter=None)` | Поиск по изображению (image-to-image). |
| `search_hybrid(self, text_query, image_path=None, limit=5, text_weight=0.7, image_weight=0.3)` | Комбинирует результаты search_text и (опционально) search_image с весами. |

**Утилиты**

| Метод | Описание |
|-------|----------|
| `get_collection_stats(self)` | Возвращает name, num_entities, schema, indexes коллекции. |
| `close(self)` | Отключается от векторной БД. |

#### load_data.py

| Элемент | Описание |
|---------|----------|
| `main()` | Читает `load_runtime_config()` → `vector_db`, `paths`, `models`, `load_data`. Вызывает `select_text_model(cfg)` для автовыбора embedding-модели. Создаёт `MultimodalRAG` с параметрами из конфига, `create_collection(drop_existing=...)`, загружает JSONL из `paths.chunked_path` (sync/async по `load_data.use_async`), выводит статистику и метаданные эмбеддингов. |

#### query.py

| Элемент | Описание |
|---------|----------|
| `main()` | Читает конфиг через `load_runtime_config()`. Проверяет Milvus через `check_vector_db_server`. Модель берёт из метаданных коллекции; при отсутствии — `select_text_model(cfg)` или `get_default_embedding_model()`. Интерактивное меню: поиск по тексту (1), по изображению (2), гибридный (3), статистика (4), выход (5). Лимит результатов — `query.default_limit`. |

#### query_test.py

| Элемент | Описание |
|---------|----------|
| `main()` | Аналогично `query.py`: конфиг из `rag_runtime.json`, проверка Milvus, модель из метаданных коллекции или автовыбор. Выполняет один `search_text` с запросом из `query_test.search_text` и лимитом `query_test.limit`. CLIP не загружается (`load_image_model=False`). |

#### test_connection.py

| Элемент | Описание |
|---------|----------|
| `main()` | Читает `config/rag_runtime.json`, подключается к Milvus, выводит базы и коллекции в **default** (как load_data/query). Проверяет наличие коллекции из конфига и число записей. |

---

### 4. scripts/update_model_profiles.py

| Функция | Описание |
|---------|----------|
| `update_model_profiles(max_hf_per_query, max_ollama_models)` | Обновляет блок `candidates` в `config/model_profiles.json`: собирает модели из `embedding_config.json`, Hugging Face API, Ollama; сохраняет pinned-модели; записывает `candidate_refresh.updated_at_utc`. |
| `main()` | CLI: `--max-hf-per-query`, `--max-ollama-models`. Запуск: `python scripts/update_model_profiles.py`. |

---

### Связи между модулями (поток данных)

```
config/rag_runtime.json
         ↓
runtime_config.load_runtime_config → resolve_repo_path
         ↓
model_selector.select_text_model (если auto_select_text_model=true)
         ↓
docx_to_md_images_1.docx_to_md_with_images
         ↑
Create_mds/generator.convert_file, main

extracted/*.md
         ↓
md_to_chunked_2.generate_chunked_file → chunk_document → PueMetadataParser
         ↑
Create_chunkeds/generator.convert_file, main

chunked/*.jsonl + image_*/
         ↓
multimodal_rag.MultimodalRAG.load_from_jsonl_folder[_async]
         ↑
load_data.main → create_collection, load_collection
         (модель: select_text_model + embedding_config.json для text_dim)

Milvus (коллекция)
         ↓
query.main / query_test.main
         → get_embedding_meta_from_collection или select_text_model
         → MultimodalRAG.search_text, search_image, search_hybrid
```

Виртуальная карта отражает текущее состояние кода проекта (классы, методы, основные функции и точки входа).