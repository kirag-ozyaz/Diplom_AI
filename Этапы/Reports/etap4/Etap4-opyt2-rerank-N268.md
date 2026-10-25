# Отчёт: опыт 2, реранкер, N = 268

Рабочий реестр **`data/rag_eval_questions/eval_questions.json`**, *N* = **268**. Полный прогон **26.10.2026** (`run_all_rerank.ps1`: infra → Hit@k rerank → generation **live** rerank → performance rerank → LLM-judge rerank).

| Этап | Время (локальное) |
|------|-------------------|
| Hit@k rerank | 26.10.2026 00:40 |
| Generation live rerank | 26.10.2026 01:26 |
| Performance rerank | 2026-10-26 02:08:23 |
| LLM-judge rerank | 2026-10-26 02:22:57 |

Модели: embedding **`intfloat/multilingual-e5-base`** (CUDA); реранкер **`BAAI/bge-reranker-v2-m3`** (CUDA); LLM **`qwen2.5:14b-instruct-q4_K_M`** (Ollama, GPU). Коллекция **`diplom_multimodal_e5_rerank`**, **2912** сущностей. Коллекции **`diplom_multimodal`** и **`diplom_multimodal_e5`** не перезаписывались.

Что изменено относительно опыта 1: префиксы E5 сохранены (`passage:` при индексации, `query:` при поиске, в хранимый текст чанка префикс не пишется). Поиск идёт в два шага: Milvus отдаёт **20** кандидатов, cross-encoder переранжирует пары (вопрос, текст чанка), наружу по-прежнему **5** чанков. Индекс Milvus тот же: HNSW, COSINE, M=8, efConstruction=200, поиск `ef=64`.

Запуск: `scripts/stage4_eval/run_all_rerank.ps1` (или по шагам `run_hitk_rerank.ps1`, `run_generation_rerank.ps1`, `run_perf_and_judge_rerank.ps1`). Конфиг: `src/preprocessing/Create_embeddings/Rerank/rag_runtime_rerank.json`. Заливка отдельной коллекции: `src/preprocessing/Create_embeddings/Rerank/load_data_rerank.py`. Лог прогона: `scripts/stage4_eval/results/logs/pipeline_2026-10-26_00-35-47_rerank.log`.

---

## Итоговые результаты Hit@k

Hit@k считается уже по top-5 **после** реранкера.

| Поле | Значение |
|------|----------|
| **Реестр** | `data/rag_eval_questions/eval_questions.json` |
| **N** | **268** |
| **Hit@1** | **72,0 %** (**193 / 268**) |
| **Hit@3** | **85,4 %** (**229 / 268**) |
| **Hit@5** | **88,8 %** (**238 / 268**) |
| **Дата/время** | 26.10.2026 00:40 |
| text_model | `intfloat/multilingual-e5-base` |
| embedding_device | **cuda** |
| Префиксы | `passage:` при индексации, `query:` при поиске |
| Реранкер | `BAAI/bge-reranker-v2-m3`, ANN top-20 → top-5, CUDA |
| Источник | `scripts/stage4_eval/results/retrieval/stage4_hitk_results_rerank.json` |

Промахи Hit@5: **30** вопросов (на **14** меньше, чем у опыта 1).

---

## Generation (live, полный RAG)

Milvus (`diplom_multimodal_e5_rerank`) + реранкер + Ollama, в контекст top-5 после реранка, префикс запроса `query:`. Скрипт: `scripts/stage4_eval/generation/eval_rag_generation.py`, режим **live**, выход `stage4_gen_eval_results_rerank.json`.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | **Дата прогона** | 26.10.2026 01:26 |
| — | **N** | 268 |
| `citation_rate` | Эталонный пункт в ответе или в контексте | **88,8 %** |
| `citation_in_answer_rate` | Эталонный пункт в тексте ответа | **74,6 %** |
| `citation_in_context_rate` | Эталонный пункт среди найденных чанков | **88,8 %** |
| `groundedness_avg` | Опора ответа на контекст (0–1) | **0,908** |
| `relevance_avg` | Соответствие ответа эталонному пункту (0–1) | **0,839** |
| `duration_avg_sec` | Средняя длительность запроса | **10,15 с** |
| — | Ошибок live | **0** |

Вопрос **id=1** в этом прогоне завершился успешно (~100 с на первом запросе: холодный старт embedding, реранкера и Ollama). В Hit@k для id=1: `hit@1` = true.

Среднее время запроса выше, чем у опыта 1 (**6,91 с**): на каждый вопрос добавляется проход cross-encoder по 20 кандидатам.

---

## Performance (нагрузочный тест Ollama)

Упрощённый промпт к Ollama, параллельность 3; **не** latency полного RAG (Milvus + реранкер + LLM). Файл: `scripts/stage4_eval/results/generation/stage4_performance_metrics_rerank.json`.

| Метрика | Значение |
|---------|----------|
| TTFT (среднее) | **18,73** с |
| TPS (среднее) | **38,77** ток/с |
| Latency avg | **27,83** с |
| Latency p95 | **41,51** с |
| Latency p99 | **50,48** с |
| RPS | **0,11** зап/с |
| Availability | **100,0 %** |
| Успешных запросов | 268 / 268 |

Цифры близки к опыту 1: этот шаг не ходит в Milvus и реранкер не вызывает.

---

## LLM-as-a-Judge

Судья: та же модель Ollama. На каждый вопрос — **шаблонный** контекст и ответ по `expected_clause` (не текст из прогона live generation и не выдача реранкера). Файл: `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics_rerank.json`.

| Метрика | Значение |
|---------|----------|
| Faithfulness (среднее) | **0,4396** |
| Answer relevancy (среднее) | **0,1888** |
| Context recall (среднее) | **0,4933** |
| Оценено без сбоя HTTP | **267 / 268** |

Сбой вызова судьи: вопрос **id=178** (в логе строка `ОШИБКА`, в оценку подставлены нули). Методика судьи не менялась, поэтому сдвиг относительно опыта 1 не относится к реранкеру.

---

## Сравнение с опытом 1

Паспорт предыдущего прогона: `Etap4-opyt1-e5-N268.md` (25.10.2026, `run_all_e5.ps1`). Тот же реестр, те же эмбеддинги и префиксы E5, коллекция без реранкера `diplom_multimodal_e5`. Опыт 0 (18.10.2026, без префиксов и без реранкера): Hit@5 **81,3 %** (218/268).

| Метрика | Опыт 1 E5 (25.10.2026) | Опыт 2 реранкер (26.10.2026) |
|---------|------------------------|------------------------------|
| Hit@1 | 60,1 % (161/268) | **72,0 %** (193/268) |
| Hit@3 | 78,0 % (209/268) | **85,4 %** (229/268) |
| Hit@5 | 83,6 % (224/268) | **88,8 %** (238/268) |
| citation_rate | 83,6 % | **88,8 %** |
| citation_in_answer_rate | 72,0 % | **74,6 %** |
| groundedness_avg | 0,908 | 0,908 |
| relevance_avg | 0,81 | **0,839** |
| duration_avg_sec (generation) | **6,91 с** | 10,15 с |
| LLM-judge faithfulness | 0,4459 | 0,4396 |
| LLM-judge relevancy | 0,1802 | 0,1888 |
| LLM-judge recall | 0,4735 | 0,4933 |
| TTFT avg (performance) | **18,31 с** | 18,73 с |

Retrieval и generation live выигрывают у опыта 1: Hit@1 **+11,9 п.п.** (на 32 вопроса больше в top-1), Hit@5 **+5,2 п.п.**, citation **+5,2 п.п.**, relevance **+0,029**. Groundedness на том же уровне. Цена — примерно **+3,2 с** на запрос полного RAG. LLM-judge на шаблонных ответах почти не сдвинулся.

---

## Артефакты

| Слой | Путь |
|------|------|
| Этот паспорт | `Этапы/Reports/etap4/Etap4-opyt2-rerank-N268.md` |
| Hit@k JSON | `scripts/stage4_eval/results/retrieval/stage4_hitk_results_rerank.json` |
| Generation JSON | `scripts/stage4_eval/results/generation/stage4_gen_eval_results_rerank.json` |
| Performance JSON | `scripts/stage4_eval/results/generation/stage4_performance_metrics_rerank.json` |
| LLM-judge JSON | `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics_rerank.json` |
| Заливка коллекции | `src/preprocessing/Create_embeddings/Rerank/load_data_rerank.py` |
| Поиск с реранкером | `src/preprocessing/Create_embeddings/Rerank/rerank_rag.py` |
