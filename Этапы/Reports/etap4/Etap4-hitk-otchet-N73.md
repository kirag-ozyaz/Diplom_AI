# Отчёт: оценка retrieval (Hit@k), N = 73

Прогон контрольного набора **73** вопросов. Дата канона: **08.10.2026 01:10**. Снимок реестра: `data/rag_eval_questions/eval_questions_74.json`.

---

## Итоговые результаты Hit@k

| Поле | Значение |
|------|----------|
| **N** | **73** |
| **Hit@1** | **68,5 %** (**50 / 73**) |
| **Hit@3** | **76,7 %** (**56 / 73**) |
| **Hit@5** | **79,5 %** (**58 / 73**) |
| **Дата/время** | 08.10.2026 01:10 |
| text_model | `intfloat/multilingual-e5-base` |
| embedding_device | **cuda** |
| Источник сводки | `scripts/stage4_eval/results/retrieval/stage4_hitk_runs.jsonl` |

Промежуточный прогон на **50** вопросах (08.10.2026 01:03): Hit@1 46,0 %, Hit@3 54,0 %, Hit@5 58,0 %.

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
| `embedding_config.json` | ключ `intfloat/multilingual-e5-base` → **768** |
| Описание схемы Milvus (при `create_collection`) | фрагмент: `text_model=intfloat/multilingual-e5-base`, `text_dim=768` в строке `description` коллекции |
| Hit@k | `get_embedding_meta_from_collection` — модель из метаданных коллекции, **совпадает с индексом** |
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
| Индексация (`_encode_text`) | **не использовались** |
| Поиск (`search_text`) | **не использовались** |

### Фильтр по разделу

| Параметр | Значение |
|----------|----------|
| `filter_chapter` | **не задан** |
| `expr` в Milvus | **None** |
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

**Критерий успеха** — `clause_in_text` в `eval_retrieval_hitk.py`: Hit@*k* = 1, если в `text` одного из первых *k* чанков (*k* ∈ {1, 3, 5}) есть совпадение (без учёта регистра): `\b{clause}\b`, `Пункт {clause}`, `п. {clause}` для эталона `expected_clause`.

Один вопрос — один `search_text`; оценивается **только retrieval**.

---

## Другие метрики на период N = 73

### Hit@k

Выполнен (таблица в начале отчёта).

### Generation и LLM-judge

| Метрика | Статус |
|---------|--------|
| `eval_rag_generation.py --mode live` | не выполнялось |
| `eval_rag_llm_judge.py` | не выполнялось |

### Performance (отдельный скрипт, не Hit@k)

Нагрузочный тест Ollama с упрощённым промптом, **без** полного RAG через Milvus:

| Поле | Значение |
|------|----------|
| Скрипт | `scripts/stage4_eval/eval_rag_performance.py` |
| Дата | 2026-10-18 00:32:34 |
| total_requests | **73** |
| successful_requests | 73 |
| availability_pct | 100,0 |
| latency_avg_sec | 8,6465 |
| ttft_avg_sec | 5,8329 |
| tps_avg | 28,23 |
| concurrency | 3 |
| Файл | `scripts/stage4_eval/results/generation/stage4_performance_metrics.json` |

---

## Артефакты

| Тип | Путь |
|-----|------|
| История Hit@k | `scripts/stage4_eval/results/retrieval/stage4_hitk_runs.jsonl` |
| Снимок вопросов | `data/rag_eval_questions/eval_questions_74.json` |
| Performance (73) | `scripts/stage4_eval/results/generation/stage4_performance_metrics.json` |
| JSON Hit@k с `details` по 73 | не архивирован отдельно |

Конфиг среды: `config/rag_runtime.json`.
