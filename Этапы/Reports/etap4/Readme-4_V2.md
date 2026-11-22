# Этап 4. Часть II. Вторая версия (проект V2): ноутбук Etap4_V2.ipynb

Ноутбук повторяет разделы 9-17 отчёта (те же номера таблиц и рисунков) и строит их по сохранённым файлам метрик, ответов и оценок судьи. Milvus и Ollama не нужны.

## Состав

| Файл или папка | Что это |
|---|---|
| `Etap4_V2.ipynb` | ноутбук второй части, уже выполнен |
| `data_V2.zip` | архив папки `data_V2` ([скачать](https://drive.google.com/uc?export=download&id=1atHoDUS384LwU2R6TTHeA4CL16oqFXz8)) |
| `data_V2/V2/results/retrieval/split/<папка>/metrics.json` | опыты 2, 3, 5 и контрольный повтор опыта 2 |
| `data_V2/V2/results/retrieval/split_extra/<папка>/metrics.json` | опыты 1 и 4 |
| `data_V2/V2/results/generation/answers/*_rerank50/` | ответы модели по выдаче опыта 4: `answers.jsonl`, `run.json` |
| `data_V2/V2/results/generation/judge/*_rerank50/` | оценки судьи: `judgments.jsonl`, `judge_metrics.json`, `run.json` |
| `data_V2/V2/results/generation/answers/*_refusal/`, `judge/*_refusal/` | то же для 48 вопросов без ответа в ПУЭ |
| `data_V2/V2/data/rag_eval_questions/` | `eval_questions_split.json` (720 вопросов), `eval_qrels_split.json` (эталон), `eval_questions_refusal.json` (48 вопросов) |
| `data_V2/V2/data/chunked_merged_manual/` | корпус V2: 46 файлов `*.chunked.jsonl` (без изображений) |
| `data_V2/scripts/stage4_eval/results/retrieval/` | результаты V1 для сравнения в разделе 13.6 |

Опыт определяется по настройкам внутри `metrics.json`, а не по имени папки; берётся последний прогон на 720 вопросах с `qrels_version = split-720-exact-text-v1`. Раздел 14.7 «Пример работы в режиме вопрос-ответ» выводит записи из `answers.jsonl` и `judgments.jsonl` (вопрос, поданные фрагменты, ответ, время, оценка судьи). Выдача `retrieval.json` (62-68 МБ на прогон) и журналы в пакет не входят.

## Как открыть

**Google Colab.** Загрузить `Etap4_V2.ipynb` и выполнить все ячейки: первая ячейка установит `plotly` и скачает `data_V2.zip` по прямой ссылке.

**Другой компьютер (Python 3.9+).** `Etap4_V2.ipynb` и папка `data_V2` в одной папке, затем:

```
pip install jupyter plotly pandas
jupyter notebook Etap4_V2.ipynb
```

**Внутри репозитория Diplom_AI.** Флаги в ячейке подготовки: `RUN_LIVE = True` заново выполняет поиск по коллекциям Milvus, `RUN_EVAL = True` пересчитывает метрики из `retrieval.json` (создаётся новая папка, старые файлы не меняются). Конфигурации V2 используют `device: cuda`.

## Как пересобрать data_V2

Из корня репозитория:

```
python V2/scripts/collect_data_V2.py
python V2/scripts/collect_data_V2.py --out D:/tmp/data_V2
```

По умолчанию копирует в `Этапы/Reports/etap4/data_V2`: последний прогон каждого опыта, последние папки `*_rerank50` и `*_refusal` в answers и judge, вопросы, корпус и файлы V1 для раздела 13.6. Скрипт только копирует и в конце печатает, что скопировано и чего не нашлось.
