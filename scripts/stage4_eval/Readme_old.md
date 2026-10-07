Команды из **корня проекта** (`X:\Учеба_УИИ\Итоговы_Проект`), venv по желанию:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 0. (Опционально) GPU / конфиг

```powershell
python scripts\compute_detect.py
python scripts\compute_detect.py --apply-config
```

Проверка CUDA / Docker / Ollama:

```powershell
.\scripts\test_cudo.ps1
```

---

### 1. Инфраструктура

**Всё для этапа 4 (Milvus + Ollama):**

```powershell
python scripts\start_report_docker.py
```

**Только Milvus** (достаточно для Hit@k):

```powershell
python scripts\start_milvus.py
```

**Ollama** (нужен для live generation):

```powershell
python scripts\start_ollama.py --pull
```

Проверка Milvus: `docker compose ps` в `infra\milvus`.

---

### 2. Retrieval — Hit@1 / Hit@3 / Hit@5

```powershell
python scripts\eval_retrieval_hitk.py
```

**Артефакты:**  
`Этапы\Reports\etap4\retrieval\stage4_hitk_results.json`, `stage4_hitk_chart.png`, `stage4_hitk_report.png`, история в `stage4_hitk_runs.jsonl`.  
После прогона обновляется §5.3 в `Readme-4.md` (при ошибке вручную: `python scripts\update_readme4_eval_docs.py`).

**Вопросы:** `Этапы\Reports\etap4\data\stage4_eval_questions.json`.

---

### 3. Generation — citation / groundedness / relevance

**Полный live RAG** (Milvus `:19530` + Ollama `:11434`):

```powershell
python scripts\eval_rag_generation.py --mode live
```

**С LLM-judge** (дольше):

```powershell
python scripts\eval_rag_generation.py --mode live --llm-judge
```

**Без Docker** (офлайн по chunked, с опорой на уже посчитанный Hit@k):

```powershell
python scripts\eval_rag_generation.py --mode mock
```

**Дозапуск после обрыва** (скрипт перезапишет JSON только по оставшимся id — для полного отчёта лучше сначала сохранить бэкап или потом собрать 25 вопросов вручную):

```powershell
python scripts\eval_rag_generation.py --mode live --start-id 23
```

**Артефакт:** `Этапы\Reports\etap4\generation\stage4_gen_eval_results.json`.

---

### Типичный порядок для полного набора метрик

```powershell
python scripts\start_milvus.py
python scripts\start_ollama.py --pull
python scripts\eval_retrieval_hitk.py
python scripts\eval_rag_generation.py --mode live
```

Альтернатива одной командой на Docker: `python scripts\start_report_docker.py`, затем два `eval_*` как выше.