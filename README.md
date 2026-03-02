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
       ▼  [sentence-transformers/all-MiniLM-L6-v2]
       │
┌──────────────┐
│ embeddings/  │  ←  ./embeddings/
│ (Chroma DB)  │      • chroma.sqlite3, Milvus, Qdrant
└──────┬───────┘      • index/
       │
       ▼  [RAG-запрос]
┌──────────────┐
│ Telegram-бот │  ←  Поиск → Релевантные чанки → LLM (Llama 3.1 8B)
│  (Ollama)    │      → Структурированный ответ с ссылками на ПУЭ/ПТЭЭП
└──────────────┘
```

## Структура проекта

```
energy_norms_bot/
├── infra/                              # Инфраструктура и развертывание
│   ├── docker/                         # (в разработке)
│   │   ├── Dockerfile.bot              # Dockerfile для Telegram-бота
│   │   ├── Dockerfile.preprocessing    # Dockerfile для скриптов обработки
│   │   ├── docker-compose.yml          # Основной compose для всех сервисов
│   │   └── .env.example                # Пример переменных окружения
│   ├── docker.attu/                    # Docker для Attu UI
│   │   └── start-attu.bat              # Скрипт запуска Attu UI для Milvus
│   ├── milvus/
│   │   ├── docker-compose.yml          # Compose для Milvus (etcd, minio, standalone)
│   │   ├── .env.example                # Путь к томам (для SSD: DOCKER_VOLUME_DIRECTORY)
│   │   └── Readme.md                   # Запуск, Attu, перенос на SSD, пересборка БД
│   ├── ollama/                         # (в разработке)
│   └── info.md                         # Общая информация по инфраструктуре
├── src/                                # Исходный код приложения
│   ├── bot/                            # Telegram-бот (в разработке)
│   ├── preprocessing/                  # Модули предобработки документов
│   │   ├── Create_mds/
│   │   │   ├── docx_to_md_images_1.py  # Конвертация DOCX → Markdown с изображениями
│   │   │   └── generator.py            # Массовая обработка документов
│   │   ├── Create_chunkeds/
│   │   │   ├── md_to_chunked_2.py      # Сегментация Markdown → JSONL chunks
│   │   │   └── generator.py            # Массовая обработка чанков
│   │   ├── Create_embeddings/
│   │   │   ├── multimodal_rag.py       # Класс MultimodalRAG для работы с Milvus
│   │   │   ├── load_data.py            # Загрузка данных в векторную БД
│   │   │   ├── query.py                # Интерактивный поиск по базе
│   │   │   ├── query_test.py           # Тестовый поиск
│   │   │   ├── test_connection.py      # Проверка подключения к Milvus
│   │   │   └── embedding_config.json   # Конфигурация моделей эмбеддингов
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
├── config/                             # (в разработке)
├── Этапы/                              # Отчеты по этапам проекта
│   └── Reports/
│       ├── Readme-1.md
│       ├── Readme-2.md
│       └── Readme-3.md
├── .gitignore
└── README.md
```

---

## Виртуальная карта кода приложения

Карта классов, методов, функций и связей между модулями проекта.

### Обзор модулей

| Модуль | Назначение |
|--------|------------|
| `src/preprocessing/Create_mds/` | Конвертация DOCX → Markdown с изображениями |
| `src/preprocessing/Create_chunkeds/` | Сегментация Markdown → чанки (JSONL) с метаданными ПУЭ |
| `src/preprocessing/Create_embeddings/` | Multimodal RAG: эмбеддинги, Milvus, поиск по тексту и изображениям |

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

**Файлы:** `multimodal_rag.py`, `load_data.py`, `query.py`, `query_test.py`, `test_connection.py`, `embedding_config.json`

#### embedding_config.json

| Назначение | Описание |
|------------|----------|
| Конфиг эмбеддингов | Словарь `text_model_dim` (модель → размерность), `default_text_model`, `default_dim`. Используется для подстановки `text_dim` при инициализации RAG и в `get_default_embedding_model()` при отсутствии метаданных коллекции. |

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
| `__init__(...)` | конструктор | Параметры: milvus_host/port, collection_name, text_model_name, clip_model_name, device_text/clip, base_data_path, image_encode_workers, batch_chunk_workers, load_image_model, text_dim (опционально — при None берётся из `embedding_config.json` по text_model_name). Вызывает `_connect_milvus`, `_load_text_model`, при необходимости `_load_clip_model`. |
| `_check_milvus_available(host, port, timeout)` | @staticmethod | Проверяет доступность Milvus по сокету; используется внутренне. |
| `check_milvus_server(host, port, timeout)` | @staticmethod | Публичная проверка доступности Milvus (port — строка или число). Для скриптов query, query_test и т.д. Возвращает bool. |
| `_connect_milvus(self)` | private | Проверяет доступность через `_check_milvus_available`, подключается к Milvus по host:port; при недоступности — выход из процесса. |
| `_load_text_model(self, model_name, device)` | private | Загрузка SentenceTransformer для текстовых эмбеддингов. |
| `_load_clip_model(self, model_name, device)` | private | Загрузка CLIP (open_clip) для эмбеддингов изображений. |

**Коллекция и индексы**

| Метод | Описание |
|-------|----------|
| `create_collection(self, drop_existing=True)` | Создаёт коллекцию в Milvus (поля: id, chunk_id, text_vector, image_vector, text, image_paths, source_file, chapter, has_image), индексы HNSW для text_vector и image_vector. |
| `load_collection(self)` | Загружает коллекцию в память для поиска; проверяет совпадение text_model/text_dim с метаданными. |

**Метаданные эмбеддингов**

| Метод | Тип | Описание |
|-------|-----|----------|
| `_parse_embedding_meta(description)` | @staticmethod | Извлекает из строки описания коллекции (description) `text_model` и `text_dim` по regex; возвращает dict или None. |
| `get_collection_embedding_meta(self)` | instance | Возвращает метаданные эмбеддингов текущей коллекции. |
| `get_embedding_meta_from_collection(cls, milvus_host, milvus_port, collection_name)` | @classmethod | Подключается к Milvus и читает метаданные коллекции без создания экземпляра RAG. |

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
| `load_from_jsonl_folder(self, jsonl_folder, batch_size, skip_existing, ...)` | Синхронная загрузка: читает JSONL из папки, кодирует текст и изображения, вставляет батчи в Milvus. |
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
| `close(self)` | Отключается от Milvus. |

#### load_data.py

| Элемент | Описание |
|---------|----------|
| `main()` | Вычисляет `chunked_root = ROOT / "data" / "chunked"`. Задаёт `text_model_name` в коде (например `intfloat/multilingual-e5-base`; можно заменить на `get_default_embedding_model()`). Создаёт `MultimodalRAG` с `base_data_path=chunked_root`, text_dim подставляется из `embedding_config.json` по `text_model_name`. Вызывает `create_collection(drop_existing=True)`, затем `load_from_jsonl_folder` или `load_from_jsonl_folder_async` (use_async=True по умолчанию), `load_collection`, выводит статистику и метаданные эмбеддингов, вызывает `rag.close()`. |

#### query.py

| Элемент | Описание |
|---------|----------|
| `main()` | Задаёт milvus_host/port, collection_name, base_data_path="data". Сначала проверяет сервер через `check_milvus_server` (из multimodal_rag); при недоступности — выход. Читает метаданные через `get_embedding_meta_from_collection`; при отсутствии — `get_default_embedding_model()`. Инициализирует `MultimodalRAG`, вызывает `load_collection`, интерактивное меню: поиск по тексту (1), по изображению (2), гибридный (3), статистика (4), выход (5). |

#### query_test.py

| Элемент | Описание |
|---------|----------|
| `main()` | Импортирует `check_milvus_server` из multimodal_rag. Проверяет сервер через `check_milvus_server(host, port)`, при недоступности — выход. Получает метаданные через `get_embedding_meta_from_collection` или `get_default_embedding_model()`, создаёт RAG с `load_image_model=False`, загружает коллекцию, выполняет один тестовый `search_text`, выводит результаты и закрывает RAG. |

#### test_connection.py

| Элемент | Описание |
|---------|----------|
| Скрипт | Подключается к Milvus (`connections.connect`), при необходимости создаёт БД `test_db` и проверяет список коллекций (`utility.list_collections()`). Утилитарный скрипт без классов. |

---

### Связи между модулями (поток данных)

```
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
         (text_dim из embedding_config.json при необходимости)

Milvus (коллекция)
         ↓
query.main / query_test.main → get_embedding_meta_from_collection или get_default_embedding_model
         → MultimodalRAG.search_text, search_image, search_hybrid
```

Виртуальная карта отражает текущее состояние кода проекта (классы, методы, основные функции и точки входа).