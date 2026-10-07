# Hit@k — теория и применение в проекте

**Проект:** RAG по ПУЭ, этап 4 (первая точность retrieval).  
**Код оценки:** `scripts/stage4_eval/eval_retrieval_hitk.py`

---

## 1. Что это

**Hit@k** (также *Hit Rate@k*, *Hits@K*) — метрика **ранжированного поиска**, не параметр нейросети.

Вопрос метрики: *попал ли хотя бы один релевантный документ в первые k результатов?*

Для одного запроса *q*:

- **hit@k(q) = 1**, если релевантный документ есть в top-*k*;
- **hit@k(q) = 0** иначе.

По *N* запросам:

**Hit@k = (1 / N) · Σ hit@k(q)**

В прототипе: *N* — число записей в `stage4_eval_questions.json`, один эталонный пункт ПУЭ (`Clause`) на вопрос, *k* ∈ {1, 3, 5}.

| Метрика | Смысл |
|---------|--------|
| Hit@1 | Эталон на **1-м** месте |
| Hit@3 | Эталон в **тройке** |
| Hit@5 | Эталон в **пятёрке** |

Всегда: **Hit@1 ≤ Hit@3 ≤ Hit@5**.

---

## 2. Зачем в этом проекте

Модели эмбеддингов и LLM **не дообучались** на ПУЭ. График loss/accuracy по эпохам неприменим.

«Первая точность распознавания» этапа 4 — это качество **retrieval**: нашёлся ли нужный пункт норматива среди top-*k* чанков, которые затем идут в LLM. Если retrieval промахнулся, генератор отвечает по чужому контексту.

---

## 3. Откуда в теории (не авторская метрика)

Название Hit@k / Hits@K пришло из ранжирования и рекомендаций. Математика старше: это частный случай метрик **information retrieval** для **ранжированной** выдачи.

### 3.1. Классический IR — Precision@k и Recall@k

**Источник:** Manning C. D., Raghavan P., Schütze H. *Introduction to Information Retrieval*. Cambridge University Press, 2008. **Глава 8. Evaluation in information retrieval.**  
Русский перевод: *Введение в информационный поиск*, изд. «Вильямс», 2011 — `Manning_2011_Vvedenie_v_informatsionnyj_poisk.djvu`.  
Файл (гл. 8, EN): `Manning_2008_IR_ch8_evaluation.pdf`  
Онлайн: https://nlp.stanford.edu/IR-book/

Для поиска с ранжированием смотрят не весь корпус, а **первые k** документов:

- **Precision@k** — какая доля из k результатов релевантна;
- **Recall@k** — какая доля *всех* релевантных документов попала в эти k.

Если у запроса **ровно один** релевантный документ (здесь: один `Clause`):

- Recall@k = 1, если он в top-*k*, иначе 0;
- среднее по запросам **совпадает с Hit@k**.

В этой постановке **Hit@k ≡ Recall@k**.

Precision@k при одном эталоне равна 1/*k* при попадании и 0 при промахе: она зависит от размера выдачи и хуже читается как «доля успешных вопросов». Для RAG нужен бинарный факт: *дошёл ли нужный пункт до генератора*.

### 3.2. Нейропоиск / QA — top-k retrieval accuracy

**Источник:** Karpukhin V. et al. *Dense Passage Retrieval for Open-Domain Question Answering*. EMNLP 2020.  
Файл: `Karpukhin_2020_DPR.pdf`  
https://arxiv.org/abs/2004.04906

В статье retriever оценивают **top-k retrieval accuracy**: доля вопросов, у которых ответ содержится среди top-*k* найденных пассажей. Это ближайший аналог Hit@k для RAG.

### 3.3. Зачем retrieval в RAG

**Источник:** Lewis P. et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020.  
Файл: `Lewis_2020_RAG.pdf`  
https://arxiv.org/abs/2005.11401

Ответ LLM строится по найденным фрагментам. Hit@k измеряет, есть ли шанс ответить по правильной норме.

---

## 4. Как считается в коде

Скрипт: `python scripts/stage4_eval/eval_retrieval_hitk.py` (см. `scripts/stage4_eval/README.md`).

1. Вопрос из `Этапы/Reports/etap4/data/stage4_eval_questions.json` (формулировки можно брать из билетов Tests24 — см. `manual/tests24_electro_safety.md`, сырые JSON в `data/tests24/`).
2. Один вызов `search_text` (лимит ≥ 5).
3. Успех, если в поле `text` одного из первых *k* чанков есть номер пункта (`1.1.4`, `п. 1.1.4`, `Пункт 1.1.4`).

Оценивается **только retrieval**, не качество текста ответа LLM.

Текст для Word-отчёта также включён в `Этапы/Reports/etap4/Readme-4.md` (п. 4.4).
