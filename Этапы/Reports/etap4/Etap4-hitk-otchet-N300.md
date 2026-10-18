# Отчёт: оценка этапа 4, N = 300 (полный контур)

Рабочий реестр **`data/rag_eval_questions/eval_questions.json`**, *N* = **300**. Прогон **18.10.2026** (цепочка `run_all.ps1`: Hit@k → generation live → performance → LLM-judge). Параметры Milvus и embedding — те же, что в архивных прогонах 38/73; меняется состав вопросов и выполняются все слои метрик.

---

## Итоговые результаты Hit@k

| Поле | Значение |
|------|----------|
| **Реестр** | `data/rag_eval_questions/eval_questions.json` |
| **N** | **300** |
| **Hit@1** | **12,3 %** (**37 / 300**) |
| **Hit@3** | **23,0 %** (**69 / 300**) |
| **Hit@5** | **28,0 %** (**84 / 300**) |
| **Дата/время** | 18.10.2026 12:15 |
| text_model | `intfloat/multilingual-e5-base` |
| embedding_device | **cuda** |
| Записей в коллекции | **2912** |
| Источник | `scripts/stage4_eval/results/retrieval/stage4_hitk_results.json` |

---

## Данные и чанкинг

| Параметр | Значение |
|----------|----------|
| Исходные чанки | `data/chunked/*.jsonl` |
| Пайплайн | `src/preprocessing/Create_chunkeds/` (Markdown → JSONL) |
| Правило сегментации | **один `Clause` → один чанк** (как в `Create_chunkeds`) |
| Загрузка в Milvus | `src/preprocessing/Create_embeddings/load_data.py` |

---

## Версия embedding в коллекции

| Источник | Значение |
|----------|----------|
| Модель поиска и индекса | **`intfloat/multilingual-e5-base`** |
| Размерность | **768** |
| `embedding_config.json` | `intfloat/multilingual-e5-base` → 768 |
| Milvus `description` | `text_model=intfloat/multilingual-e5-base`, `text_dim=768` |
| Hit@k | `get_embedding_meta_from_collection` — совпадает с индексом |
| `normalize_embeddings` | **True** |

---

## Параметры поиска (Milvus)

| Параметр | Значение |
|----------|----------|
| host:port | `localhost:19530` |
| collection | `diplom_multimodal` |
| Поле ANN | `text_vector` |
| Индекс | **HNSW**, **COSINE**, `M: 8`, `efConstruction: 200` |
| Поиск | COSINE, **`ef: 64`**, `limit` = **5** |

### E5-префиксы и фильтр

| Параметр | Значение |
|----------|----------|
| `query:` / `passage:` | **не использовались** |
| `filter_chapter` / `expr` | **не использовались** |
| `section` в реестре | в Milvus **не передаётся** |

---

## Методика расчёта Hit@k

| Параметр | Значение |
|----------|----------|
| Скрипт | `scripts/stage4_eval/eval_retrieval_hitk.py` |
| `search_limit` | **5** |
| Метрики | **Hit@1, Hit@3, Hit@5** |
| Retrieval | **только** `rag.search_text(q, limit=5)` |
| Не использовалось | hybrid, image, rerank, LLM в этом шаге |

**Критерий успеха** — `clause_in_text` в `eval_retrieval_hitk.py`: в `text` одного из первых *k* чанков (*k* ∈ {1, 3, 5}) эталон `expected_clause` как `\b{clause}\b`, `Пункт {clause}` или `п. {clause}` (без учёта регистра).

---

## Generation (live, полный RAG)

Milvus + Ollama, контекст top-5. Скрипт: `eval_rag_generation.py`, режим **live**.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | **Дата прогона** | 18.10.2026 12:48 |
| — | **N** | 300 |
| `citation_rate` | Доля вопросов с эталонным пунктом в ответе или в контексте | **28,0 %** |
| `citation_in_answer_rate` | Эталонный пункт упомянут в тексте ответа | **15,0 %** |
| `citation_in_context_rate` | Эталонный пункт есть среди найденных чанков | **28,0 %** |
| `groundedness_avg` | Опора ответа на контекст (0–1) | **0,89** |
| `relevance_avg` | Соответствие ответа эталонному пункту (0–1) | **0,317** |
| — | Файл | `scripts/stage4_eval/results/generation/stage4_gen_eval_results.json` |

---

## Performance (Ollama, не полный RAG)

Нагрузочный тест: упрощённый промпт к Ollama, **без** Milvus в том же запросе. Не заменяет latency полного контура generation.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | Скрипт | `eval_rag_performance.py` |
| — | **Дата** | 2026-10-18 13:37:36 |
| `total_requests` | Число запросов | **300** |
| `availability_pct` | Доступность (успешные запросы) | **100 %** |
| `ttft_avg_sec` | Время до первого токена (среднее) | **19,72 с** |
| `tps_avg` | Скорость генерации (ток/с) | **40,02** |
| `latency_avg_sec` | Полная задержка (среднее) | **29,36 с** |
| `latency_p95_sec` | Задержка, 95-й перцентиль | **43,50 с** |
| `rps` | Пропускная способность | **0,10** зап/с |
| `concurrency` | Параллельность | 3 |
| — | Файл | `scripts/stage4_eval/results/generation/stage4_performance_metrics.json` |

---

## LLM-as-a-Judge (оценка судьёй-моделью)

Отдельная LLM оценивает качество ответа по трём шкалам 0–1. Скрипт: `eval_rag_llm_judge.py`. Судья: **`qwen2.5:14b-instruct-q4_K_M`**.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | **Дата прогона** | 2026-10-18 13:53:34 |
| `sample_count` | Число оценённых вопросов | **300** |
| `faithfulness_avg` | **Обоснованность** — насколько ответ согласуется с переданным контекстом | **0,452** |
| `answer_relevancy_avg` | **Релевантность ответа** — насколько ответ отвечает на вопрос | **0,196** |
| `context_recall_avg` | **Полнота контекста** — насколько контекст покрывает информацию для ответа | **0,500** |
| — | Файл | `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics.json` |

Ограничение: в промпт судьи подставляется **укороченный шаблонный** контекст и ответ (не полный trace из `eval_rag_generation.py`). Для цитирования и опоры на контекст используйте метрики generation выше.

---

## Артефакты

| Слой | Путь |
|------|------|
| Hit@k JSON + `details` | `scripts/stage4_eval/results/retrieval/stage4_hitk_results.json` |
| История Hit@k | `scripts/stage4_eval/results/retrieval/stage4_hitk_runs.jsonl` |
| PNG | `stage4_hitk_chart.png`, `stage4_hitk_report.png` |
| Generation | `scripts/stage4_eval/results/generation/stage4_gen_eval_results.json` |
| Performance | `scripts/stage4_eval/results/generation/stage4_performance_metrics.json` |
| Judge | `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics.json` |

Конфиг: `config/rag_runtime.json`. Сводка по слоям: `scripts/stage4_eval/Сводка_метрик_этапа_4.md`.
