# Справочные материалы (manual)

Локальная библиотека для отчёта и защиты. В репозиторий Git попадают **только файлы `*.md`** из этой папки; PDF, DjVu и прочие носители книг хранятся у вас на диске (см. `.gitignore`).

Краткие конспекты: **`Hit_at_k.md`**, **`OpenCLIP_ViT-B-32.md`**.

---

## Markdown (в Git)

| Файл | Назначение |
|------|------------|
| `README.md` | Этот каталог |
| `Hit_at_k.md` | Hit@k: определение, формула, связь с Recall@k, применение в проекте |
| `OpenCLIP_ViT-B-32.md` | CLIP/OpenCLIP ViT-B-32: роль в `multimodal_rag`, Milvus `image_vector`, `load_image_model` |
| `tests24_electro_safety.md` | Внешние билеты ЭБ: [tests24.ru](https://tests24.ru/), [tests24.su](https://tests24.su/test-24/elektrobezopasnost/), скрипты `scripts/tests24/` |

---

## Книги и статьи (только локально, не в Git)

### Учебник по information retrieval

| Файл | Описание |
|------|----------|
| `Manning_2011_Vvedenie_v_informatsionnyj_poisk.djvu` | **Маннинг К. Д., Рагхаван П., Шютце Х. *Введение в информационный поиск*** — русский перевод того же учебника (*Introduction to Information Retrieval*). Изд. «Вильямс», Москва · Санкт-Петербург · Киев, **2011**. Удобно для защиты и цитат по-русски; гл. 8 — оценка поиска (Precision@k, Recall@k). Формат DjVu (~11 МБ). |
| `irbookonlinereading.pdf` | **Manning C. D., Raghavan P., Schütze H. *Introduction to Information Retrieval*** (Cambridge University Press, 2008) — полный текст в варианте «online reading» с сайта [nlp.stanford.edu/IR-book](https://nlp.stanford.edu/IR-book/). Тот же учебник, **английский** полный том. |
| `Manning_2008_IR_ch8_evaluation.pdf` | Та же книга, **только глава 8** (*Evaluation in information retrieval*) — удобно для цитирования в отчёте без полного тома. |

### Статьи (нейропоиск и RAG)

| Файл | Описание |
|------|----------|
| `Karpukhin_2020_DPR.pdf` | **Karpukhin V. et al. *Dense Passage Retrieval for Open-Domain Question Answering*** (EMNLP 2020). Плотные эмбеддинги для поиска пассажей; метрика **top-k retrieval accuracy** — по смыслу то же, что Hit@k при одном правильном ответе на вопрос. [arXiv:2004.04906](https://arxiv.org/abs/2004.04906) |
| `Lewis_2020_RAG.pdf` | **Lewis P. et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*** (NeurIPS 2020). Архитектура RAG: сначала retrieval, затем генерация по контексту — обоснование, зачем измерять качество поиска отдельно от LLM. [arXiv:2005.11401](https://arxiv.org/abs/2005.11401) |

## Онлайн (если нет локального PDF)

- Гл. 8 IR-book: https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html  
- DPR: https://arxiv.org/abs/2004.04906  
- RAG: https://arxiv.org/abs/2005.11401  

Связь с отчётом: `Этапы/Reports/etap4/Readme-4.md`, п. **4.4** и приложения.
