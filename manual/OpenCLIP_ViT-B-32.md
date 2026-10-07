# OpenCLIP ViT-B-32 — мультимодальные эмбеддинги изображений в проекте

**Проект:** RAG по ПУЭ, коллекция Milvus `diplom_multimodal`.  
**Код:** `src/preprocessing/Create_embeddings/multimodal_rag.py` (библиотека `open_clip`).  
**Конфиг:** `config/rag_runtime.json` → `models.clip_model_name`, `models.device_clip`.

---

## 1. Что это такое

**CLIP** (*Contrastive Language–Image Pre-training*) — семейство моделей, которые сопоставляют **изображение** и **текст** в общем векторном пространстве. В проекте для картинок из ПУЭ (схемы, рисунки из DOCX→Markdown) используется реализация **OpenCLIP** с архитектурой **ViT-B/32**:

| Параметр | Значение в проекте |
|----------|-------------------|
| Имя в `open_clip` | `ViT-B-32` |
| Предобученные веса | `laion2b_e16` (датасет LAION-2B) |
| Размерность вектора изображения | **512** (`image_dim` в `MultimodalRAG`) |
| Устройство по умолчанию | **CPU** (`device_clip: "cpu"` в конфиге) |

Текстовые фрагменты ПУЭ кодируются **отдельной** моделью (SentenceTransformer, например `intfloat/multilingual-e5-base`). CLIP к тексту вопроса на этапе 4 **не применяется** — только к файлам изображений при индексации и при поиске по картинке.

---

## 2. Зачем CLIP в дипломном контуре

1. **Индексация:** при загрузке чанков в Milvus (`load_data.py`, `load_from_jsonl_folder`) для каждой записи сохраняются два вектора: `text_vector` (e5) и `image_vector` (CLIP), если в чанке есть ссылки на рисунки.
2. **Поиск по изображению:** метод `search_image` ищет ближайшие чанки по полю `image_vector` (запрос — эмбеддинг загруженного или указанного файла).
3. **Мультимодальность в перспективе:** коллекция названа `diplom_multimodal`; текстовый RAG и Hit@k на этапе 4 опираются только на `search_text` и `text_vector`.

Связь с этапами: этап 3 — подготовка MD и чанков с картинками; этап 4 — метрики **текстового** retrieval; CLIP остаётся в инфраструктуре для полной загрузки данных и будущего поиска по схемам.

---

## 3. Где задаётся в конфигурации

Фрагмент `config/rag_runtime.json` (секция `models`):

```json
"clip_model_name": "ViT-B-32",
"device_clip": "cpu"
```

**Почему CLIP на CPU:** на видеокарте с ограниченной VRAM (например, 6–8 ГБ) одновременно держат эмбеддинги текста (часто CUDA), Ollama и CLIP на GPU — риск нехватки памяти. CLIP при индексации вызывается пакетами и реже, чем текстовый encode при поиске; перенос CLIP на CPU разгружает VRAM для e5 и LLM.

---

## 4. Когда модель загружается, а когда нет

Параметр конструктора `MultimodalRAG(..., load_image_model=True|False)`.

| `load_image_model` | Поведение |
|--------------------|-----------|
| **True** | Вызывается `_load_clip_model`: загрузка OpenCLIP, сообщение `Загрузка CLIP модели: ViT-B-32`. Нужно для `load_data.py`, полного индексирования с картинками, `search_image`. |
| **False** | CLIP в память **не** загружается. В консоли: *«CLIP (модель OpenCLIP ViT-B-32 для изображений) не загружается (режим только текстового поиска)»*. Достаточно для `search_text`, Hit@k, live RAG (`rag_service`), `query_test.py`, `eval_retrieval_hitk.py`. |

Это **не ошибка**: для оценки Hit@k и ответов бота по тексту вопроса CLIP на этапе запроса не требуется. Векторы изображений в Milvus уже могли быть записаны ранее при полной загрузке с `load_image_model=True`.

---

## 5. Как устроено в Milvus

В схеме коллекции (создание в `multimodal_rag.py`):

- `text_vector` — размерность из текстовой модели (например, 768 для e5-base);
- `image_vector` — **512** float, индекс по CLIP;
- метаданные: `text`, `image_paths`, `source_file`, `has_image` и др.

Поиск по тексту: `anns_field="text_vector"`. Поиск по изображению: `anns_field="image_vector"`.

---

## 6. Основные операции в коде

| Метод | Назначение |
|-------|------------|
| `_load_clip_model` | `open_clip.create_model_and_transforms`, перенос на `device_clip`, режим `eval()` |
| `_encode_image` | Один файл → нормализованный вектор длины 512 |
| `_encode_images_batch` | Несколько путей из чанка → усреднение векторов |
| `search_image` | Запрос по `image_vector` в Milvus |
| `load_from_jsonl_folder` | Массовая загрузка чанков с текстом и изображениями |

При `load_image_model=False` вызов `_encode_image` / `search_image` завершится с `RuntimeError` с подсказкой включить загрузку CLIP.

---

## 7. Зависимости и первый запуск

- Пакет **`open_clip`** (OpenCLIP).
- Веса при первом запуске могут скачиваться с Hugging Face Hub (в логе — проверка кэша, как у текстовой модели).
- Предобработка изображений: `clip_preprocess` из `create_model_and_transforms` (resize, normalize под ViT).

---

## 8. Ссылки

- OpenCLIP: [https://github.com/mlfoundations/open_clip](https://github.com/mlfoundations/open_clip)
- Исходная идея CLIP: Radford et al., *Learning Transferable Visual Models From Natural Language Supervision* (2021)
- Текстовый поиск и Hit@k: `manual/Hit_at_k.md`
- Запуск и конфиг: `start/Readme.md`, корневой `README.md` (раздел `MultimodalRAG`)
