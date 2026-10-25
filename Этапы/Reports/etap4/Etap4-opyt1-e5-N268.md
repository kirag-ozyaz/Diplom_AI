# Отчёт: опыт 1, префиксы E5, N = 268

Рабочий реестр **`data/rag_eval_questions/eval_questions.json`**, *N* = **268**. Полный прогон **25.10.2026** (`run_all_e5.ps1`: infra → Hit@k E5 → generation **live** E5 → performance E5 → LLM-judge E5).

| Этап | Время (локальное) |
|------|-------------------|
| Hit@k E5 | 25.10.2026 21:04 |
| Generation live E5 | 25.10.2026 21:36 |
| Performance E5 | 2026-10-25 22:16:44 |
| LLM-judge E5 | 2026-10-25 22:31:33 |

Модели: embedding **`intfloat/multilingual-e5-base`** (CUDA); LLM **`qwen2.5:14b-instruct-q4_K_M`** (Ollama, GPU). Коллекция **`diplom_multimodal_e5`**, **2912** сущностей. Базовая коллекция **`diplom_multimodal`** не перезаписывалась.

Что изменено относительно опыта 0: при индексации к тексту чанка добавляется префикс `passage:`, при поиске к вопросу — `query:`. В хранимый текст чанка префикс не пишется. Индекс Milvus тот же: HNSW, COSINE, M=8, efConstruction=200, поиск `ef=64`, limit 5.

Запуск: `scripts/stage4_eval/run_all_e5.ps1` (или по шагам `run_hitk_e5.ps1`, `run_generation_e5.ps1`, `run_perf_and_judge_e5.ps1`). Конфиг коллекции: `src/preprocessing/Create_embeddings/E5/rag_runtime_e5.json`. Лог прогона: `scripts/stage4_eval/results/logs/pipeline_2026-10-25_21-03-38_e5.log`.

---

## Итоговые результаты Hit@k

| Поле | Значение |
|------|----------|
| **Реестр** | `data/rag_eval_questions/eval_questions.json` |
| **N** | **268** |
| **Hit@1** | **60,1 %** (**161 / 268**) |
| **Hit@3** | **78,0 %** (**209 / 268**) |
| **Hit@5** | **83,6 %** (**224 / 268**) |
| **Дата/время** | 25.10.2026 21:04 |
| text_model | `intfloat/multilingual-e5-base` |
| embedding_device | **cuda** |
| Префиксы | `passage:` при индексации, `query:` при поиске |
| Источник | `scripts/stage4_eval/results/retrieval/stage4_hitk_results_e5.json` |

---

## Generation (live, полный RAG)

Milvus (`diplom_multimodal_e5`) + Ollama, контекст top-5, префикс запроса `query:`. Скрипт: `scripts/stage4_eval/generation/eval_rag_generation.py`, режим **live**, выход `stage4_gen_eval_results_e5.json`.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | **Дата прогона** | 25.10.2026 21:36 |
| — | **N** | 268 |
| `citation_rate` | Эталонный пункт в ответе или в контексте | **83,6 %** |
| `citation_in_answer_rate` | Эталонный пункт в тексте ответа | **72,0 %** |
| `citation_in_context_rate` | Эталонный пункт среди найденных чанков | **83,6 %** |
| `groundedness_avg` | Опора ответа на контекст (0–1) | **0,908** |
| `relevance_avg` | Соответствие ответа эталонному пункту (0–1) | **0,81** |
| `duration_avg_sec` | Средняя длительность запроса | **6,91 с** |
| — | Ошибок live | **0** |

Вопрос **id=1** в этом прогоне завершился успешно (~49 с на первом запросе, холодный старт embedding + Ollama). В Hit@k для id=1: `hit@1` = true.

---

## Performance (нагрузочный тест Ollama)

Упрощённый промпт к Ollama, параллельность 3; **не** latency полного RAG (Milvus + LLM). Файл: `scripts/stage4_eval/results/generation/stage4_performance_metrics_e5.json`.

| Метрика | Значение |
|---------|----------|
| TTFT (среднее) | **18,31** с |
| TPS (среднее) | **38,96** ток/с |
| Latency avg | **27,20** с |
| Latency p95 | **39,93** с |
| Latency p99 | **43,86** с |
| RPS | **0,11** зап/с |
| Availability | **100,0 %** |
| Успешных запросов | 268 / 268 |

---

## LLM-as-a-Judge

Судья: та же модель Ollama. На каждый вопрос — **шаблонный** контекст и ответ по `expected_clause` (не текст из прогона live generation). Файл: `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics_e5.json`.

| Метрика | Значение |
|---------|----------|
| Faithfulness (среднее) | **0,4459** |
| Answer relevancy (среднее) | **0,1802** |
| Context recall (среднее) | **0,4735** |
| Оценено без сбоя HTTP | **268 / 268** |

---

## Сравнение с опытом 0

Паспорт базы: `Etap4-hitk-otchet-N268.md` (прогон 18.10.2026, `run_all.ps1`). Тот же реестр, та же модель эмбеддингов, коллекция без префиксов `diplom_multimodal`.

| Метрика | Опыт 0 (18.10.2026) | Опыт 1 E5 (25.10.2026) |
|---------|---------------------|-------------------------|
| Hit@1 | 58,2 % (156/268) | **60,1 %** (161/268) |
| Hit@3 | 76,1 % (204/268) | **78,0 %** (209/268) |
| Hit@5 | 81,3 % (218/268) | **83,6 %** (224/268) |
| citation_rate | 81,3 % | **83,6 %** |
| citation_in_answer_rate | 70,9 % | **72,0 %** |
| groundedness_avg | 0,887 | **0,908** |
| relevance_avg | 0,792 | **0,81** |
| duration_avg_sec (generation) | ~7,9 с | **6,91 с** |
| LLM-judge faithfulness | 0,4347 | **0,4459** |
| LLM-judge relevancy | 0,1847 | 0,1802 |
| LLM-judge recall | 0,5060 | 0,4735 |
| TTFT avg (performance) | 18,72 с | **18,31 с** |

Retrieval и generation live выигрывают у опыта 0; LLM-judge на шаблонных ответах почти на том же уровне (методика судьи не менялась).

---

## Артефакты

| Слой | Путь |
|------|------|
| Этот паспорт | `Этапы/Reports/etap4/Etap4-opyt1-e5-N268.md` |
| Hit@k JSON | `scripts/stage4_eval/results/retrieval/stage4_hitk_results_e5.json` |
| Generation JSON | `scripts/stage4_eval/results/generation/stage4_gen_eval_results_e5.json` |
| Performance JSON | `scripts/stage4_eval/results/generation/stage4_performance_metrics_e5.json` |
| LLM-judge JSON | `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics_e5.json` |
| Заливка коллекции | `src/preprocessing/Create_embeddings/E5/load_data_e5.py` |
