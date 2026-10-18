# Отчёты по этапам диплома

Каталог `Этапы/Reports` — **тексты сдачи** по этапам (по одному основному файлу на этап).  
Тема и ТЗ с платформы (PDF/DOCX): `Диплом/` (см. `Диплом/README.md`).

| Папка | Содержимое |
|-------|------------|
| `etap1/` | Отчёт этапа 1 — `Readme-1.md` |
| `etap2/` | Отчёт этапа 2 — `Readme-2.md` |
| `etap3/` | Ноутбук этапа 3 — `Readme-3 (ver. 4).ipynb` |
| `etap4/` | Отчёт этапа 4 — `Readme-4.md` |
| `trash/` | Устаревшие версии ноутбуков и черновики |

## Этап 4 — где лежат исходники отчёта

| Путь | Назначение |
|------|------------|
| `Этапы/Reports/etap4/Readme-4.md` | **Текст отчёта** для Word (разделы 1–8) |
| `Этапы/Reports/etap4/Etap4-hitk-svod.md` | **Свод** Hit@k (38 / 73 / 300, хронология, слои) |
| `Этапы/Reports/etap4/Etap4-hitk-otchet-N38.md` | Отчёт Hit@k, *N* = **38** (вход / итог) |
| `Этапы/Reports/etap4/Etap4-hitk-otchet-N73.md` | Отчёт Hit@k, *N* = **73** (+ performance на 73) |
| `Этапы/Reports/etap4/Etap4-hitk-otchet-N300.md` | Полный прогон *N* = **300** (Hit@k + generation + perf + judge) |
| `Этапы/Reports/etap4/Readme-4 (ver. 2).ipynb` | Исполняемый отчёт (Docker, Hit@k, демо Milvus) |
| `scripts/stage4_eval/Сводка_метрик_этапа_4.md` | Перечень метрик и ссылки на JSON |
| `scripts/stage4_eval/results/` | JSON/PNG прогонов (retrieval, generation) |
| `data/rag_eval_questions/eval_questions.json` | Рабочий реестр контрольных вопросов (300) |
| `scripts/stage4_eval/results/retrieval/` | Hit@k: JSON, история, PNG |
| `scripts/stage4_eval/results/generation/` | Метрики generation, performance, LLM-judge |

Пути в коде: `scripts/lib/report_paths.py`. Запуск метрик: `scripts/stage4_eval/README.md`.

После изменения реестра из 300 вопросов нужен **полный пересчёт** метрик; числа в `Readme-4.md` (§5.3, §7) должны соответствовать JSON в `scripts/stage4_eval/results/`.
