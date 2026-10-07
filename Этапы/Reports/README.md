# Отчёты по этапам диплома

Каталог `Этапы/Reports` — тексты и артефакты сдачи по этапам курса.

| Папка | Содержимое |
|-------|------------|
| `etap1/` | Отчёт этапа 1 — `Readme-1.md` |
| `etap2/` | Отчёт этапа 2 — `Readme-2.md` |
| `etap3/` | Ноутбук этапа 3 — `Readme-3 (ver. 4).ipynb` |
| `etap4/` | Этап 4 (RAG, Hit@k): `Readme-4.md`, `Readme-4 (ver. 2).ipynb`, подкаталоги с метриками |
| `trash/` | Устаревшие версии ноутбуков и черновики |

## Этап 4 — структура `etap4/`

| Путь | Назначение |
|------|------------|
| `Readme-4.md` | Мастер-текст для Word (разделы 1–8) |
| `Readme-4 (ver. 2).ipynb` | Исполняемый отчёт (Docker, Hit@k, демо Milvus) |
| `data/stage4_eval_questions.json` | Тестовые вопросы и эталонные пункты ПУЭ (Hit@k) |
| `retrieval/stage4_hitk_results.json` | Последний прогон Hit@k |
| `retrieval/stage4_hitk_runs.jsonl` | История прогонов Hit@k |
| `retrieval/stage4_hitk_chart.png`, `stage4_hitk_report.png` | Графики для Word |
| `generation/stage4_gen_eval_results.json` | Метрики generation / citation / groundedness |
| `generation/Etap4-gen-metrics.md` | Пояснение к прогону generation |

Пути в коде: `scripts/report_paths.py`.

**Как прогнать метрики (команды, Docker, дозапуск):** `scripts/stage4_eval/README.md`.
