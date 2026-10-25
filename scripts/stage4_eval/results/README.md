# Результаты прогонов stage4_eval

JSON и PNG по метрикам RAG (Hit@k, generation, performance, LLM-judge). Пути в коде: `scripts/lib/report_paths.py`.

| Каталог | Содержимое |
|---------|------------|
| `retrieval/` | `stage4_hitk_results.json` (опыт 0), `stage4_hitk_results_e5.json` (опыт 1), `stage4_hitk_results_rerank.json` (опыт 2), `stage4_hitk_runs.jsonl`, графики PNG |
| `generation/` | метрики generation, performance, judge; опыт 1 — суффикс `_e5`, опыт 2 — `_rerank`; `Etap4-gen-metrics.md` |
| `logs/` | `pipeline_<дата>.log` (опыт 0), `pipeline_<дата>_e5.log` (опыт 1), `pipeline_<дата>_rerank.log` (опыт 2) |

Текст отчёта для сдачи: `Этапы/Reports/etap4/Readme-4.md` (§5.4 — сводная таблица). Вопросы: `data/rag_eval_questions/`.
