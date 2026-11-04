# Архив этапа 4: итоговый ноутбук и исправленный Readme-4

| Файл | Куда положить в репозитории | Что это |
|---|---|---|
| `Etap4_final.ipynb` | `Этапы/Reports/etap4/` | Итоговый ноутбук этапа 4. Сохранён без выводов; таблицы и графики появляются после *Run All*. Читает только файлы `scripts/stage4_eval/results/`, Milvus/Ollama не нужны. Повторный прогон оценки — флаг `RUN_LIVE = True` (по умолчанию `False`). |
| `Readme-4.md` | `Этапы/Reports/etap4/` (заменить) | Исправленный отчёт: дата 28.10.2026, три опыта (1–3), серия прогонов опыта 1, MRR/nDCG, исправлены генерация опыта 1 и пути к скриптам, отмечена проблема `scripts/lib`, ссылка на `Etap4_final.ipynb`. |
| `Analiz_noutbuka_etap4.md` | `Этапы/Reports/etap4/` | Разбор старого `Readme-4 (ver. 2).ipynb`: удалить / добавить / изменить. |
| `build_stage4_summary.py`, `README_build_stage4_summary.md` | `scripts/stage4_eval/reports/` | Автоматическая сводка всех метрик трёх опытов (md/csv/json). |
| `Otchet_etap4_v3.docx`, `Otchet_etap4_v3.md` | — | Отчёт преподавателю, версия 3. |

Старый `Readme-4 (ver. 2).ipynb` рекомендуется перенести в `Этапы/Reports/trash/`.
