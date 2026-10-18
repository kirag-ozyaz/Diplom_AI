# Контрольные вопросы для оценки RAG (ПУЭ)

Реестры JSON для Hit@k, generation и LLM-judge. Пути в коде: `scripts/lib/report_paths.py` (`STAGE4_QUESTIONS` и снимки).

**Поля записи:** `id` — номер внутри файла (1…N); `registry_id` — **глобальный** ключ (`Q-####`), не сбрасывается при переносе между реестрами. Сводный `eval_questions_pue_all.json` хранит исходные `registry_id` из дочерних наборов.

| Файл | N | Диапазон `registry_id` (глобальный) |
|------|---|-------------------------------------|
| `eval_questions_pue_expanded_final.json` | 559 | Q-0001…Q-0559 (expanded + no_test24) |
| `eval_questions_pue300_no_test24_final.json` | 259 | Q-0301…Q-0559 (снимок; дублирует хвост expanded) |
| `eval_questions_300_final.json` | 268 | Q-0560…Q-0827 |
| `eval_questions_374_final.json` | 337 | Q-0828…Q-1164 |
| `eval_questions_pue_all.json` | 1164 | объединение четырёх наборов выше |
| `eval_questions_base38.json` | 38 | ранний снимок (Q-001…) |
| `eval_questions_74.json` | 74 | ранний снимок (Q-001…) |

Архив и черновики: `old/`. Рабочий путь для скриптов по умолчанию — `eval_questions.json` (при необходимости копия из `*_final`).

Текст отчёта: `Этапы/Reports/etap4/Readme-4.md`. Артефакты прогонов: `scripts/stage4_eval/results/`.
