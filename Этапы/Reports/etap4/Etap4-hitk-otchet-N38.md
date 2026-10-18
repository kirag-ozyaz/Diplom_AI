# Отчёт: оценка retrieval (Hit@k), N = 38

Прогон контрольного набора **38** вопросов. Дата канона: **08.10.2026 00:48**.

---

## Итоговые результаты

| Поле | Значение |
|------|----------|
| **Реестр** | `data/rag_eval_questions/eval_questions_base38.json` |
| **N** | **38** |
| **Hit@1** | **55,3 %** (**21 / 38**) |
| **Hit@3** | **63,2 %** (**24 / 38**) |
| **Hit@5** | **68,4 %** (**26 / 38**) |
| **Дата/время** | 08.10.2026 00:48 (повторы 07.10.2026 22:11, 23:40 — те же %) |
| Источник сводки | `scripts/stage4_eval/results/retrieval/stage4_hitk_runs.jsonl` |

---

## Данные и чанкинг

| Параметр | Значение |
|----------|----------|
| Исходные чанки | `data/chunked/*.jsonl` |
| Пайплайн | `src/preprocessing/Create_chunkeds/` (Markdown → JSONL) |
| Правило сегментации | **один `Clause` → один чанк** (как в `Create_chunkeds`) |
| Загрузка в Milvus | `src/preprocessing/Create_embeddings/load_data.py` |
| Записей в коллекции на дату прогона | **2912** |

---

## Версия embedding в коллекции

| Источник | Значение |
|----------|----------|
| Модель поиска и индекса | **`intfloat/multilingual-e5-base`** |
| Размерность вектора | **768** |
| `embedding_config.json` | ключ `intfloat/multilingual-e5-base` → **768**; `default_text_model` в файле — запасной вариант, **не** использовался при наличии метаданных коллекции |
| Описание схемы Milvus (при `create_collection`) | фрагмент: `text_model=intfloat/multilingual-e5-base`, `text_dim=768` в строке `description` коллекции |
| Hit@k | `eval_retrieval_hitk.py` читает модель через `get_embedding_meta_from_collection` — **та же**, что заложена в индекс |
| Нормализация векторов | `normalize_embeddings=True` |
| Устройство при прогоне | **cuda** |

---

## Параметры поиска (Milvus)

| Параметр | Значение |
|----------|----------|
| host:port | `localhost:19530` |
| collection | `diplom_multimodal` |
| Поле ANN | `text_vector` |
| Индекс при создании | **HNSW**, метрика **COSINE**, `M: 8`, `efConstruction: 200` |
| `search_params` при запросе | COSINE, **`ef: 64`** |
| `limit` (`search_limit`) | **5** |

### E5-префиксы

| Этап | `query:` / `passage:` |
|------|------------------------|
| Индексация (`_encode_text`) | **не использовались** — текст чанка как есть |
| Поиск (`search_text`) | **не использовались** — текст вопроса как есть |

### Фильтр по разделу

| Параметр | Значение |
|----------|----------|
| `filter_chapter` | **не задан** |
| `expr` в Milvus | **None** (поиск по всей коллекции) |
| `section` в JSON вопросов | **не используется** в фильтре |

---

## Методика расчёта Hit@k

| Параметр | Значение |
|----------|----------|
| Скрипт | `scripts/stage4_eval/eval_retrieval_hitk.py` |
| `search_limit` | **5** |
| Считаемые метрики | **только Hit@1, Hit@3, Hit@5** |
| Вызов retrieval | **только** `rag.search_text(q, limit=5)` |
| Не использовалось | `search_hybrid`, `search_image`, rerank, Ollama |

**Критерий успеха** — функция `clause_in_text` в `eval_retrieval_hitk.py`: для вопроса с эталоном `expected_clause` значение Hit@*k* = 1, если в поле `text` **хотя бы одного** из первых *k* чанков ( *k* ∈ {1, 3, 5} ) есть совпадение по одному из шаблонов (регистронезависимо): `\b{clause}\b`, `Пункт {clause}`, `п. {clause}`.

Один вопрос — один проход `search_text`; оценивается **только retrieval**, не генерация LLM.

---

## Другие метрики этапа 4 (на этом N)

| Метрика | Статус |
|---------|--------|
| Generation (live) | не выполнялось |
| LLM-as-a-Judge | не выполнялось |
| Performance | не выполнялось |

---

## История повторных прогонов

| Дата/время | Hit@1 | Hit@3 | Hit@5 |
|------------|-------|-------|-------|
| 07.10.2026 22:11 | 55,3 % | 63,2 % | 68,4 % |
| 07.10.2026 23:40 | 55,3 % | 63,2 % | 68,4 % |
| 08.10.2026 00:48 | 55,3 % | 63,2 % | 68,4 % |

---

## Артефакты

| Тип | Путь |
|-----|------|
| История Hit@k | `scripts/stage4_eval/results/retrieval/stage4_hitk_runs.jsonl` |
| JSON с `details` по 38 вопросам | не архивирован отдельно |

Конфиг среды: `config/rag_runtime.json` (секции `vector_db`, `models`).
