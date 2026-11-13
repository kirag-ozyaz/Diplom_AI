# Этап 4, редакция v6.3 (проект V2): техническое описание

Этот файл сопровождает `Otchet_etap4_v6.3.docx` и `Etap4_final_v6.3.ipynb`. По сравнению с v6.2 добавлены оценка ответов LLM-судьёй (раздел 8 ниже) и проверка правильного отказа на вопросах без ответа в ПУЭ (раздел 9). Файлы предыдущих редакций в этой папке не изменялись.

## 1. Что сделано

10–11.11.2026 выполнено пять прогонов поиска и один контрольный повтор на наборе из 720 вопросов: 268 исходных вопросов и 452 части X.1, X.2 …. Корпус: `V2/data/chunked_merged_manual`, 46 файлов, 3146 чанков, главы 1.1–1.9 выверены вручную. Эталон: `eval_qrels_split.json`, версия `split-720-exact-text-v1`, 1733 дословных абзаца, все найдены в чанках.

| Опыт | Режим и конфиг | Коллекция | Кандидатов для реранкера | CLIP |
|---|---|---|---|---|
| 1. Без префиксов | `base`, `pipeline_manual_merged_split_extra.json` | `diplom_v2_noprefix` | — | нет |
| 2. Префиксы E5 | `base`, `pipeline_manual_merged_split.json` | `diplom_v2_base` | — | нет |
| Контроль | `e5`, `pipeline_manual_merged_split.json` | `diplom_v2_e5` | — | нет |
| 3. Реранкер, 20 | `rerank`, `pipeline_manual_merged_split.json` | `diplom_v2_rerank` | 20 | нет |
| 4. Реранкер, 50 | `rerank`, `pipeline_manual_merged_split_extra.json` | `diplom_v2_rerank` | 50 | нет |
| 5. Реранкер, 50 + CLIP | `rerank --with-clip`, `pipeline_manual_merged_split.json` | `diplom_v2_rerank` + `diplom_v2_clip` (390 изображений) | 50 (глубина CLIP) | да, RRF k = 60 |

Общее для всех опытов: `intfloat/multilingual-e5-base` (768), Milvus AUTOINDEX/COSINE, `device` и `clip_device` = `cuda`, batch 16, глубина выдачи 20, k = 1, 3, 5, 10, 20. Реранкер `BAAI/bge-reranker-v2-m3` с `max_length=512`.

## 2. Итог на 268 исходных вопросах (зачёт по дословному абзацу)

| Опыт | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Все факты в топ-5 |
|---|---|---|---|---|---|---|
| 1. Без префиксов | 68.7 | 84.7 | 88.8 | 94.0 | 0.778 | 86.2 |
| 2. Префиксы E5 | 71.6 | 86.2 | 91.0 | 94.4 | 0.800 | 88.1 |
| Контроль | 71.3 | 86.6 | 91.4 | 94.8 | 0.800 | 88.4 |
| 3. Реранкер, 20 | 88.1 | 95.1 | 95.5 | 96.3 | 0.915 | 92.5 |
| 4. Реранкер, 50 | 89.9 | 97.0 | 98.5 | 98.9 | 0.937 | 96.3 |
| 5. Реранкер, 50 + CLIP | 90.3 | 97.0 | 98.1 | 98.5 | 0.938 | 95.9 |

Таблицы по всем 720 вопросам, по частям, по разделам и сравнение с первым проектом считает ноутбук.

## 3. Файлы результатов

Каждый прогон пишет папку с `retrieval.json` (выдача, 62–68 МБ) и `metrics.json`.

| Опыт | Папка результатов | Drive id `metrics.json` | Создан (UTC+4) |
|---|---|---|---|
| 1 | `V2/results/retrieval/split_extra/…` | `13FW283IsJPN342uFZnMEg0y9e0-lSOOq` | 11.11 00:05 |
| 2 | `V2/results/retrieval/split/…` | `1cEH1pG_cE1-EdTyP9FRfXvxyOqoqX1Ho` | 10.11 22:16 |
| Контроль | `V2/results/retrieval/split/…` | `1qvrMOVA9dSIh1coXfh-Y4bX62xGDII-5` | 10.11 22:21 |
| 3 | `V2/results/retrieval/split/…` | `1sOv-5vKb_78JnaStacKO75T7xHYY5vyA` | 10.11 22:51 |
| 4 | `V2/results/retrieval/split_extra/…` | `1mvSPR5LjS6GPxS71o7uiElfGmF_tv7zq` | 11.11 00:25 |
| 5 | `V2/results/retrieval/split/…` | `1alE-xCdOIrCE2UfwdQ9avMZfMA7RPjTR` | 10.11 23:34 |

Логи: `V2/results/logs/1_base.log`, `2_e5.log`, `3_rerank.log`, `4_load_clip.log`, `5_rerank_clip.log`, `6_noprefix.log`, `7_rerank50.log`.

Данные первого проекта для сравнения (раздел 5.6 отчёта): `scripts/stage4_eval/results/retrieval/stage4_rank_results_base.json`, `..._e5.json`, `..._rerank.json` (прогоны 28.10.2026).

Конфиги: `V2/configs/pipeline_manual_merged_split.json` (Drive id `1hJSuLfD5St9leP63YuZEVZYIS4MrecGo`) и `V2/configs/pipeline_manual_merged_split_extra.json` (Drive id `1gVxrYUYUGrlhp1O-HRSyWfMnAKE-p4fb`; результаты в `split_extra`, в нём режим `base` без префиксов в `diplom_v2_noprefix` и `rerank` с 50 кандидатами).

## 4. Команды (PowerShell, корень проекта, Milvus запущен)

```
$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding=[Text.Encoding]::UTF8
New-Item -ItemType Directory -Force -Path V2\results\logs | Out-Null

python V2/scripts/run_pipeline.py all --config V2/configs/pipeline_manual_merged_split.json --mode base --allow-db-write 2>&1 | Tee-Object -FilePath V2\results\logs\1_base.log
python V2/scripts/run_pipeline.py all --config V2/configs/pipeline_manual_merged_split.json --mode e5 --allow-db-write 2>&1 | Tee-Object -FilePath V2\results\logs\2_e5.log
python V2/scripts/run_pipeline.py all --config V2/configs/pipeline_manual_merged_split.json --mode rerank --allow-db-write 2>&1 | Tee-Object -FilePath V2\results\logs\3_rerank.log
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/clip-ViT-B-32', device='cpu')"
python V2/scripts/run_pipeline.py load-clip --config V2/configs/pipeline_manual_merged_split.json --allow-db-write 2>&1 | Tee-Object -FilePath V2\results\logs\4_load_clip.log
python V2/scripts/run_pipeline.py all --config V2/configs/pipeline_manual_merged_split.json --mode rerank --reuse-collection --with-clip 2>&1 | Tee-Object -FilePath V2\results\logs\5_rerank_clip.log
python V2/scripts/run_pipeline.py all --config V2/configs/pipeline_manual_merged_split_extra.json --mode base --allow-db-write 2>&1 | Tee-Object -FilePath V2\results\logs\6_noprefix.log
python V2/scripts/run_pipeline.py all --config V2/configs/pipeline_manual_merged_split_extra.json --mode rerank --reuse-collection 2>&1 | Tee-Object -FilePath V2\results\logs\7_rerank50.log
```

Пересчёт метрик по сохранённой выдаче без Milvus (пишет новую папку, старые файлы не трогает):

```
python V2/scripts/run_pipeline.py evaluate --config V2/configs/pipeline_manual_merged_split.json --mode rerank --input V2/results/retrieval/split/<папка>/retrieval.json
```

Флаги: `--allow-db-write` создаёт коллекцию и останавливается, если она уже есть (ничего не удаляет); `--reuse-collection` использует готовую коллекцию и сверяет её подпись (модель, размерность, префиксы, нормировка, хеши чанков и ресурсов; устройство в подпись не входит).

## 5. Ноутбук

`Etap4_final_v6.3.ipynb` положить в корень проекта или в любую его подпапку и запустить все ячейки. Нужны `plotly` и `IPython`. Ноутбук сам находит корень (папку с `V2/results/retrieval`), собирает все `metrics.json` из `V2/results/retrieval/split*`, определяет опыт по `search_settings` внутри файла и берёт последний прогон каждого опыта. Графики интерактивные (plotly). Флаги: `RUN_LIVE = True` заново выполняет поиск по готовым коллекциям, `RUN_EVAL = True` пересчитывает метрики из `retrieval.json`. Раздел 6 ноутбука читает последние папки `V2/results/generation/answers/*_rerank50/`, `judge/*_rerank50/` (6.4, оценки судьи и таблица критических ошибок) и `answers/*_refusal/`, `judge/*_refusal/` (6.5, набор на отказ); Ollama для этого не нужна. Результат ручной проверки отказов задан в ноутбуке списком `MANUAL_NOT_OK`.

## 6. Метрики

- Hit@k: среди первых k есть чанк с дословным эталонным абзацем (оценка 2 в qrels).
- Зачёт по пункту (`clause`): среди первых k есть чанк обязательного пункта; используется для сравнения с первым проектом.
- MRR: среднее 1/позиции первого попадания по выдаче глубиной 20 (MRR@10 при сравнении с v5).
- nDCG@5: относительно идеального порядка эталонных чанков.
- Все факты в топ-5: все обязательные абзацы эталона в первых пяти чанках.
- Изображения в зачёт не входят (`resources_mode = text_only`), поэтому опыт 5 оценивает влияние CLIP только на порядок текстовых чанков.

## 7. Генерация ответов (редакция v6.2)

13.11.2026, 00:14–01:16 (UTC+4), рабочая станция автора. Скрипт `V2/scripts/generation/generate.py` (ZIP `V2_генерация_1_11.zip`, Drive id `18LJ125Xb0LP3DANE868isjZaOhQvWHZi`). Вход — сохранённая выдача опыта 4 `V2/results/retrieval/split_extra/20261111_000608_110945/retrieval.json` (создана 11.11 00:25), Milvus не нужен.

| Параметр | Значение |
|---|---|
| Модель | `qwen2.5:14b-instruct-q4_K_M`, Ollama `http://localhost:11434` |
| Системная подсказка | `PUE_SYSTEM` из первого проекта (`src/rag/rag_service.py`), без изменений |
| Подаётся модели | только вопрос и первые 5 фрагментов выдачи |
| temperature / num_predict | 0.2 / 512 (как в первом проекте) |
| num_ctx | 8192 (в первом проекте не задавалось) |
| Обрезка фрагмента | более 4000 символов |

| Показатель | Все 720 | Исходные 268 | Части 452 |
|---|---|---|---|
| Ответов / ошибок | 720 / 0 | 268 / 0 | 452 / 0 |
| Время ответа, с: среднее / медиана | 5.2 / 4.3 | 6.3 / 5.1 | 4.6 / 4.0 |
| Токенов в запросе / ответе (среднее) | 1917 / 143 | 1755 / 177 | 2014 / 123 |
| Ответ содержит номер пункта | 706 (98.1 %) | 267 (99.6 %) | 439 (97.1 %) |
| Пункт не из заголовков поданных фрагментов | 70 | 33 | 37 |
| Явный отказ | 5 | 2 | 3 |
| Ответ упёрся в 512 токенов | 10 | 6 | 4 |
| Есть обрезанный фрагмент | 69 | 24 | 45 |

Общее время 62.8 мин, 37.5 токена/с. Отказы: 71.12, 72.8, 82.3, 164, 206 (164 и 206 — промахи поиска из раздела 5.8 отчёта). Упёрлись в лимит: 7, 21, 49, 78.4, 92, 115.1, 130, 130.2, 188.4, 190. «Пункт не из заголовков» — не обязательно ошибка: номер может быть взят из текста фрагмента; проверяется судьёй.

Команды (PowerShell, корень проекта):

```
$R = (Get-ChildItem V2\results\retrieval\split_extra -Recurse -Filter retrieval.json | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
python V2/scripts/generation/generate.py --input $R --label rerank50 2>&1 | Tee-Object -FilePath V2\results\logs\8_generate.log
$A = (Get-ChildItem V2\results\generation\answers -Directory -Filter *_rerank50 | Sort-Object Name | Select-Object -Last 1).FullName + '\answers.jsonl'
python V2/scripts/generation/judge.py --answers $A --label rerank50 2>&1 | Tee-Object -FilePath V2\results\logs\9_judge.log
```

## 8. Оценка ответов LLM-судьёй (редакция v6.3)

`judge.py` из ZIP 1_11, модель `qwen2.5:14b-instruct-q4_K_M`, temperature 0. Судья видит вопрос, обязательные факты эталона, пять фрагментов и ответ; по каждому критерию 0/1/2. Шкала в таблице — средний балл / 2.

Прогон 13.11.2026 20:46–22:05 (UTC+4), 79 мин, 720 из 720 оценены, сбоев нет. Папка `V2/results/generation/judge/<папка>_rerank50/`: `judgments.jsonl` (Drive id `1joEY1cKvuu31q_pay6UW_CiwSQtsUjm_`), `judge_metrics.json` (`1LSn_tTIahwZVFHYCGu5BLxziibvGRPsy`), `run.json` (`1_kfUsS01K_nf-SYyxn1kIw8CCl68EspR`). Лог `V2/results/logs/9_judge.log`.

| Показатель | Все 720 | Исходные 268 | Части 452 |
|---|---|---|---|
| Факты | 92.9 % | 90.5 % | 94.3 % |
| Числа и единицы | 92.2 % | 91.4 % | 92.7 % |
| Исключения и условия | 90.8 % | 89.7 % | 91.4 % |
| Источник (пункт) | 95.0 % | 94.6 % | 95.2 % |
| Обоснованность отказа | 95.8 % | 95.7 % | 95.9 % |
| Итоговый балл | 93.3 % | 92.4 % | 93.9 % |
| Все критерии = 2 | 85.1 % | 81.7 % | 87.2 % |
| Все критерии ≥ 1 | 94.6 % | 95.1 % | 94.3 % |
| Критическая ошибка | 19 (2.6 %) | 7 (2.6 %) | 12 (2.7 %) |
| Отказ (по судье) | 9 (1.3 %) | 4 (1.5 %) | 5 (1.1 %) |

Разработка (571): итог 93.6 %, отложенные (149): 92.2 %. Критические ошибки: эталонный пункт не подан поиском — 7.4, 24, 35, 71.11, 71.13, 78.7, 115.2, 164, 206; пункт подан, ошибка генерации — 5.3, 34.5, 56.7, 129.2, 129.6, 149, 175, 202.1, 202.2, 246. Часть отметок может быть ошибкой самого судьи (например, 5.3); вручную эти 19 ответов ещё не проверены.

## 9. Вопросы без ответа в ПУЭ (редакция v6.3)

Из ZIP 1_12: `V2/data/rag_eval_questions/eval_questions_refusal.json` — 48 вопросов R01–R48 (`answerability = not_in_pue`): другие нормы 16, новые технологии 14, смежные темы 4, вне темы 14. Каждый вопрос проверен поиском ключевых слов по 3146 чанкам (ПУЭ и Приказ 811) и семантическим поиском multilingual-e5-base; вопросы с найденным ответом исключены. `V2/scripts/generation/refusal_search.py` — поиск конфигурацией опыта 4.

Прогоны 13.11.2026 (UTC+4): поиск 22:21, генерация 22:37 (среднее 6.4 с на ответ, без обрывов), судья 22:44–22:48. Логи `10_refusal_search.log`, `11_refusal_generate.log`, `12_refusal_judge.log`. Файлы: `refusal_retrieval/<папка>_refusal/retrieval.json` (Drive id `1aFuE7kfONaqqKu06wTKvUmbAbC3CBojO`), `answers/<папка>_refusal/answers.jsonl` (`13dRlJYE0eswMHP6CfxHyq-QDXlsKqWqg`), `judge/<папка>_refusal/judgments.jsonl` (`1Lh93Agmb9dD7PAReJH7fcH66ZyPNX2vZ`) и `judge_metrics.json` (`199TZPdNWJ1WCwrcb5HM4YFaAX-78_d8X`).

| Категория | Вопросов | Правильный отказ (судья) | Ручная строгая проверка |
|---|---|---|---|
| Другие нормы | 16 | 16 | 16 |
| Новые технологии | 14 | 14 | 11 |
| Смежные темы | 4 | 2 | 2 |
| Вне темы | 14 | 14 | 14 |
| Всего | 48 | 46 (95.8 %) | 43 (89.6 %) |

Не засчитаны при ручной проверке: R17, R22, R28 (отказ, но затем посторонние пункты как ответ; судья поставил 2), R26 (тёплый пол — требования 7.1.88 без оговорки), R32 (тепловизионный контроль — «раз в год, п. 63 ПУЭ», на деле пункт Приказа 811 о другом). R47 судья отметил как выдумку, но ответ корректен (ссылка на 1.7.155).

Команды (PowerShell, корень проекта, из `КОМАНДЫ_отказ_1_12.txt`):

```
python V2/scripts/generation/refusal_search.py 2>&1 | Tee-Object -FilePath V2\results\logs\10_refusal_search.log
$RR = (Get-ChildItem V2\results\generation\refusal_retrieval -Directory -Filter *_refusal | Sort-Object Name | Select-Object -Last 1).FullName + '\retrieval.json'
python V2/scripts/generation/generate.py --input $RR --questions V2/data/rag_eval_questions/eval_questions_refusal.json --label refusal 2>&1 | Tee-Object -FilePath V2\results\logs\11_refusal_generate.log
$AR = (Get-ChildItem V2\results\generation\answers -Directory -Filter *_refusal | Sort-Object Name | Select-Object -Last 1).FullName + '\answers.jsonl'
python V2/scripts/generation/judge.py --answers $AR --label refusal 2>&1 | Tee-Object -FilePath V2\results\logs\12_refusal_judge.log
```

Судья — та же модель, что отвечала, поэтому его оценки вспомогательные; на наборе на отказ он мягче человека (46 против 43).

## 10. Исправления по ходу прогонов

- Реранкер работал очень медленно при почти полной видеопамяти (RTX 5060 Ti 16 ГБ) и длинных чанках с таблицами. Введено `max_length=512` в `CrossEncoder` (`backend.py`).
- Модель CLIP не была в локальном кэше при `local_files_only=true`. Она скачивается один раз командой выше.
- Итоговое переранжирование в прогоне с CLIP не печатало прогресс. Добавлена строка прогресса каждые 20 вопросов.
- Опыты 1 и 4 добавлены после первых прогонов: коллекции `diplom_v2_base` и `diplom_v2_e5` настроены одинаково, а в прогоне с CLIP реранкер получал 50 кандидатов вместо 20.

## 11. Чего в этой редакции нет

Ручной проверки ответов основного набора (выборка и все 19 критических ошибок) для оценки согласия судьи с человеком; судьи другой моделью; замера времени поиска и переранжирования. Это следующий шаг (раздел 9 отчёта).
