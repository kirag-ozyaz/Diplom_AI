# Скрипты проекта

```
scripts/
├── lib/              report_paths.py — единые пути отчёта и eval
├── infra/            Docker Milvus/Ollama, GPU, model_profiles
├── reports/          синхронизация ноутбука этапа 4
├── check/            smoke-тесты Ollama, CUDA, RAG
├── stage4_eval/      метрики RAG → results/retrieval|generation/
└── tests24/          билеты tests24 → сборка eval_questions
```

| Каталог | Назначение |
|---------|------------|
| **`lib/`** | Общие модули: `report_paths.py` (пути отчёта и eval), `notebook_bootstrap.py` |
| **`infra/`** | Docker / Milvus / Ollama, `compute_detect.py`, `update_model_profiles.py` |
| **`reports/`** | `sync_readme4_notebook.py` — синхронизация ноутбука этапа 4 с `Readme-4.md` |
| **`check/`** | Проверки GPU/CUDA, тесты Ollama и RAG |
| **`stage4_eval/`** | Метрики RAG (Hit@k, generation, judge); результаты в `stage4_eval/results/` |
| **`tests24/`** | Выгрузка билетов и сборка вопросов для eval |

Примеры (из корня репозитория):

```powershell
python scripts/infra/start_report_docker.py
python scripts/stage4_eval/eval_retrieval_hitk.py
python scripts/reports/sync_readme4_notebook.py
```

Пути этапа 4 в коде: `from report_paths import ...` (каталог `lib/` должен быть в `sys.path`; скрипты `stage4_eval` добавляют его через `_bootstrap.py`).
