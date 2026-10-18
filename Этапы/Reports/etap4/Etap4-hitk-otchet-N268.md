# Отчёт: оценка этапа 4, N = 268 (полный контур)

Рабочий реестр **`data/rag_eval_questions/eval_questions.json`**, *N* = **268** (источник: `eval_questions_300_final.json`, `registry_id` Q-0560…). Прогон **18.10.2026** (`run_all.ps1`: infra → Hit@k → generation **live** → performance → LLM-judge).

| Этап | Время (локальное) |
|------|-------------------|
| Hit@k | 18.10.2026 16:58 |
| Generation live | 18.10.2026 17:28 |
| Performance | 2026-10-18 18:10:17 |
| LLM-judge | 2026-10-18 18:24:52 |

Модели: embedding **`intfloat/multilingual-e5-base`** (CUDA); LLM **`qwen2.5:14b-instruct-q4_K_M`** (Ollama, GPU). Коллекция **`diplom_multimodal`**, **2912** сущностей.

---

## Итоговые результаты Hit@k

| Поле | Значение |
|------|----------|
| **Реестр** | `data/rag_eval_questions/eval_questions.json` |
| **N** | **268** |
| **Hit@1** | **58,2 %** (**156 / 268**) |
| **Hit@3** | **76,1 %** (**204 / 268**) |
| **Hit@5** | **81,3 %** (**218 / 268**) |
| **Дата/время** | 18.10.2026 16:58 |
| text_model | `intfloat/multilingual-e5-base` |
| embedding_device | **cuda** |
| Источник | `scripts/stage4_eval/results/retrieval/stage4_hitk_results.json` |

---

## Generation (live, полный RAG)

Milvus + Ollama, контекст top-5. Скрипт: `scripts/stage4_eval/generation/eval_rag_generation.py`, режим **live**.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | **Дата прогона** | 18.10.2026 17:28 |
| — | **N** | 268 |
| `citation_rate` | Эталонный пункт в ответе или в контексте | **81,3 %** |
| `citation_in_answer_rate` | Эталонный пункт в тексте ответа | **70,9 %** |
| `citation_in_context_rate` | Эталонный пункт среди найденных чанков | **81,3 %** |
| `groundedness_avg` | Опора ответа на контекст (0–1) | **0,887** |
| `relevance_avg` | Соответствие ответа эталонному пункту (0–1) | **0,792** |
| — | Файл | `scripts/stage4_eval/results/generation/stage4_gen_eval_results.json` |

Согласованность с Hit@5: при `hit5=True` из `stage4_hitk_results.json` в логе generation выводятся также hit1/hit3; метрика `relevance` использует флаг **retrieval_hit5**.

---

## Performance (Ollama, упрощённый промпт)

Нагрузочный тест **без** Milvus в том же HTTP-запросе; **до 3 параллельных** запросов к Ollama. Не заменяет сквозную задержку live generation.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | Скрипт | `scripts/stage4_eval/generation/eval_rag_performance.py` |
| — | **Дата** | 2026-10-18 18:10:17 |
| `total_requests` | Число запросов | **268** |
| `successful_requests` | Успешные | **268** |
| `availability_pct` | Доступность | **100 %** |
| `concurrency` | Параллельность | **3** |
| `ttft_avg_sec` | Время до первого токена (среднее) | **18,72 с** |
| `tps_avg` | Скорость decode (ток/с) | **38,19** |
| `latency_avg_sec` | Полная задержка ответа Ollama (среднее) | **27,81 с** |
| `latency_p95_sec` | Задержка, p95 | **39,58 с** |
| `latency_p99_sec` | Задержка, p99 | **47,62 с** |
| `rps` | Пропускная способность (оценка) | **0,11** зап/с |
| `total_tokens_generated` | Сгенерировано токенов | **92 837** |
| — | Файл | `scripts/stage4_eval/results/generation/stage4_performance_metrics.json` |

**Интерпретация:** высокий **TPS** (~38 ток/с) отражает скорость decode 14B на GPU; большой **TTFT** — prefill длинных вопросов и очередь при параллельности 3.

---

## LLM-as-a-Judge

Скрипт: `eval_rag_llm_judge.py`. Судья: **`qwen2.5:14b-instruct-q4_K_M`**. Оценка **по одному** запросу на вопрос.

| Поле JSON | По-русски | Значение |
|-----------|-----------|----------|
| — | **Дата** | 2026-10-18 18:24:52 |
| `sample_count` | N | **268** |
| `faithfulness_avg` | Обоснованность ответа контекстом (0–1) | **0,435** |
| `answer_relevancy_avg` | Релевантность ответа вопросу (0–1) | **0,185** |
| `context_recall_avg` | Полнота контекста (0–1) | **0,506** |
| — | Файл | `scripts/stage4_eval/results/generation/stage4_llm_judge_metrics.json` |

**Ограничение:** в промпт судьи подставляются **шаблонные** контекст и ответ по `expected_clause`, а не фактический trace из generation live. Для цитирования и опоры на контекст опирайтесь на метрики **generation** выше; judge — вспомогательный слой методики этапа 4.

---

## Сравнение с прогоном N=300 (18.10.2026 12:15)

| Метрика | N=300 (старый реестр в `eval_questions.json`) | N=268 (текущий прогон) |
|---------|-----------------------------------------------|-------------------------|
| Hit@1 | 12,3 % | **58,2 %** |
| Hit@5 | 28,0 % | **81,3 %** |
| citation_rate | 28,0 % | **81,3 %** |
| relevance_avg | 0,317 | **0,792** |

Различие связано с **составом реестра** (268 вопросов из `eval_questions_300_final` / Q-0560…), а не со сменой коллекции Milvus.

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

Конфиг: `config/rag_runtime.json`. Запуск: `scripts/stage4_eval/run_all.ps1`.
