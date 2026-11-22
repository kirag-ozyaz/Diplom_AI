# Этап 4. Часть I. Первая версия (проект V1): ноутбук Etap4_V1.ipynb

Ноутбук повторяет разделы 1-8 отчёта (те же номера таблиц и рисунков) и строит их по сохранённым файлам результатов. Milvus, Docker и Ollama не нужны.

## Состав

| Файл или папка | Что это |
|---|---|
| `Etap4_V1.ipynb` | ноутбук первой части, уже выполнен (результаты видны без запуска) |
| `data_V1.zip` | архив папки `data_V1` с данными для ноутбука ([скачать](https://drive.google.com/uc?export=download&id=1EjVjrsfOimN1qWrP6Py3TZYu9-2gQpay)) |
| `data_V1/config/rag_runtime.json`, `data_V1/src/preprocessing/Create_embeddings/E5/rag_runtime_e5.json`, `.../Rerank/rag_runtime_rerank.json` | настройки опытов 1, 2, 3 |
| `data_V1/data/chunked/` | корпус V1: 43 файла `*.chunked.jsonl` и папки изображений `image_*` |
| `data_V1/data/corpus_inventory.json` | опись корпуса |
| `data_V1/data/rag_eval_questions/` | наборы вопросов, в том числе `eval_questions.json` (268 вопросов) и версии для серии прогонов опыта 1 |
| `data_V1/scripts/stage4_eval/results/retrieval/` | Hit@k, MRR и nDCG (`stage4_hitk_*`, `stage4_rank_results_*`, `stage4_hitk_runs.jsonl`) |
| `data_V1/scripts/stage4_eval/results/generation/` | качество ответа, скорость модели и вторая оценка (`stage4_gen_eval_results*`, `stage4_performance_metrics*`, `stage4_llm_judge_metrics*`); раздел 5.9 «Пример работы в режиме вопрос-ответ» берёт записи из `stage4_gen_eval_results*.json` |

## Как открыть

**Google Colab.** Загрузить `Etap4_V1.ipynb` (Файл, Загрузить блокнот) и выполнить все ячейки. Первая ячейка сама установит `plotly`, если его нет, скачает `data_V1.zip` по прямой ссылке и распакует рядом с ноутбуком.

**Другой компьютер (Python 3.9+).** Положить `Etap4_V1.ipynb` и папку `data_V1` (распакованный `data_V1.zip`) в одну папку, затем:

```
pip install jupyter plotly pandas
jupyter notebook Etap4_V1.ipynb
```

и выполнить все ячейки (Run All). Если папки `data_V1` рядом нет, ноутбук скачает архив сам (нужен интернет).

**Внутри репозитория Diplom_AI.** Ноутбук находит корень проекта (папку, где есть `scripts/stage4_eval/results`) и читает файлы оттуда. Повторный прогон оценки включается флагом `RUN_LIVE = True` (нужны Docker, Milvus и Ollama).

## Как пересобрать data_V1

Из корня репозитория:

```
python scripts/stage4_eval/collect_data_V1.py
python scripts/stage4_eval/collect_data_V1.py --out D:/tmp/data_V1
```

По умолчанию файлы копируются в `Этапы/Reports/etap4/data_V1`. Скрипт только копирует и в конце печатает, что скопировано и чего не нашлось.
