# Этап 4 — метрики generation / citation / groundedness

**Дата прогона:** 07.10.2026 00:10  
**Режим:** `mock` (запрошен `mock`)  
**Скрипт:** `Diplom_AI/scripts/eval_rag_generation.py`  
**Набор:** те же 25 вопросов, что Hit@k (`Этапы/Reports/stage4_eval_questions.json`)  
**Выравнивание по Hit@5:** True (из `stage4_hitk_results.json`)

## Инфраструктура

| Сервис | Статус на этой машине |
|--------|------------------------|
| Docker | **нет** (`docker: command not found`) |
| Milvus (`:19530`) | недоступен |
| Ollama (`:11434`) | недоступен |

Попытка `python scripts/start_milvus.py` / `start_ollama.py` — блокируется отсутствием Docker.  
Поэтому выполнен **mock**-прогон (не live RAG).

### Как запустить live у себя

```bash
cd Diplom_AI
python scripts/start_milvus.py
python scripts/start_ollama.py --pull
python scripts/eval_rag_generation.py --mode live \
  --out /workspace/stage4_gen_eval_results.json --llm-judge
```

Mock / dry-run (без Docker):

```bash
python scripts/eval_rag_generation.py --mode mock --out /workspace/stage4_gen_eval_results.json
```

## Метрики (mock, N=25)

| Метрика | Значение | Смысл |
|---------|----------|--------|
| **Citation rate** | **48.0%** | эталонный Clause есть в ответе или в retrieved-контексте |
| Citation in answer | 48.0% | Clause упомянут в тексте ответа |
| Citation in context | 48.0% | Clause есть в top-k контексте |
| **Groundedness (avg)** | **1.0** | доля предложений ответа, опирающихся на контекст (токенный overlap; отказ → 1.0) |
| **Relevance (avg)** | **0.74** | соответствие эталонному пункту (1.0 cite в ответе; 0.5 честный отказ при miss Hit@5) |
| LLM-judge avg | None | только при `--llm-judge` + live Ollama |

### Интерпретация mock

Mock **симулирует** generation с опорой на Hit@5 из уже посчитанного retrieval:
- Hit@5 = true → ответ цитирует эталонный чанк из `data/chunked` (oracle cite);
- Hit@5 = false → отказ без эталонного пункта в контексте.

Поэтому citation ≈ Hit@5 (**48%**) — это **верхняя оценка generation при текущем retrieval**, а не замена live-прогона Ollama.

## Файлы

| Файл | Назначение |
|------|------------|
| `/workspace/Diplom_AI/scripts/eval_rag_generation.py` | скрипт оценки |
| `/workspace/stage4_gen_eval_results.json` | результаты этого прогона |
| `/workspace/Diplom_AI/Этапы/Reports/stage4_gen_eval_results.json` | копия в дереве репо (локально, **не запушено**) |
| `/workspace/Etap4-gen-metrics.md` | эта сводка |

## Blockers для live

1. Нет Docker на agent box → нельзя поднять Milvus/Ollama через `scripts/start_*.py`.
2. Порты 19530 / 11434 закрыты.
3. Без live embeddings + LLM нельзя получить реальные ответы `rag_service.answer()`.

После появления Docker/сервисов достаточно `--mode live` на том же JSON вопросов.
