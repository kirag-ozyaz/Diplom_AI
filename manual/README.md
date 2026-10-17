# Справочные материалы (manual)

Библиотека для отчёта и защиты: конспекты, методичка по оценке RAG и исходники книг/статей.

В Git идёт **вся папка**, включая `books/` (PDF и DjVu). На `manual` отдельных ограничений в `.gitignore` нет.

Связь с отчётом: `Этапы/Reports/etap4/Readme-4.md`, п. **4.4** и приложения.

---

## Markdown и Word

| Файл | Назначение |
|------|------------|
| `README.md` | Этот каталог |
| `Metodichka-RAG.md` | Методичка «Оценка качества RAG-систем»: критерии, метрики, методы, порядок оценки, приложения Б–Г |
| `Metodichka-RAG.docx` | Та же методичка в Word (для печати и правок) |
| `Hit_at_k.md` | Hit@k: определение, формула, связь с Recall@k, применение в проекте |
| `OpenCLIP_ViT-B-32.md` | CLIP/OpenCLIP ViT-B-32: роль в `multimodal_rag`, Milvus `image_vector`, `load_image_model` |
| `tests24_electro_safety.md` | Внешние билеты ЭБ: [tests24.ru](https://tests24.ru/), [tests24.su](https://tests24.su/test-24/elektrobezopasnost/), скрипты `scripts/tests24/` |
| `rclone.md` | Rclone: установка, `gdrive_kirag_3:project_rag`, **`rclone-backup.bat`** / **`rclone-restore.bat`** / **`rclone-sync.bat`**, фильтры из `.gitignore` |

---

## Книги и статьи (`books/`)

### Учебник по information retrieval

| Файл | Описание |
|------|----------|
| `Manning_2011_Vvedenie_v_informatsionnyj_poisk.djvu` | **Маннинг К. Д., Рагхаван П., Шютце Х. *Введение в информационный поиск*** — русский перевод (*Introduction to Information Retrieval*). «Вильямс», 2011. Гл. 8 — оценка поиска (Precision@k, Recall@k). |
| `irbookonlinereading.pdf` | **Manning C. D., Raghavan P., Schütze H. *Introduction to Information Retrieval*** (CUP, 2008) — полный английский текст, вариант «online reading» с [nlp.stanford.edu/IR-book](https://nlp.stanford.edu/IR-book/). |
| `Manning_2008_IR_ch8_evaluation.pdf` | Та же книга, **только глава 8** (*Evaluation in information retrieval*). |

### Статьи (нейропоиск и RAG)

| Файл | Описание |
|------|----------|
| `Karpukhin_2020_DPR.pdf` | **Karpukhin V. et al. *Dense Passage Retrieval for Open-Domain Question Answering*** (EMNLP 2020). Top-k retrieval accuracy ≈ Hit@k при одном правильном ответе. [arXiv:2004.04906](https://arxiv.org/abs/2004.04906) |
| `Lewis_2020_RAG.pdf` | **Lewis P. et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*** (NeurIPS 2020). Сначала retrieval, затем генерация. [arXiv:2005.11401](https://arxiv.org/abs/2005.11401) |

### Книги по RAG (оценка и практика)

| Файл | Описание |
|------|----------|
| `Hands_On_RAG_for_Production_Ofer_Mendelevitch,_Forrest_Sheng_Bao.pdf` | **Mendelevitch O., Bao F. S. *Hands-On RAG for Production*** (O'Reilly, 2026). Гл. 6 — оценка RAG, гл. 7 — наблюдаемость. В методичке: **[HO-RAG]**. |
| `RAG и генеративный ИИ.pdf` | **Ротман Д. *RAG и генеративный ИИ*** (Спринт Бук, 2025; ориг. *RAG-Driven Generative AI*, Packt, 2024). В методичке: **[Ротман]**. Код: [Denis2054/RAG-Driven-Generative-AI](https://github.com/Denis2054/RAG-Driven-Generative-AI), рус. адаптация — [webmakaka/RAG-Driven-Generative-AI](https://github.com/webmakaka/RAG-Driven-Generative-AI). |
| `RAG_и_генеративный_ИИ_Дэнис_Ротман2025.pdf` | Тот же Ротман, другой файл/скан; репозитории — см. строку выше. |
| `RAG-системы от теории к практике. Душкин Р.В..djvu` | **Душкин Р. В. *RAG-системы: от теории к практике*** (ДМК Пресс, 2025). Гл. 7–8 — оценка и гарды. В методичке: **[Душкин]**. |
| `ИИ_ассистенты_на_Python,_применяем_LLM,_GPT,_RAG_на_практике_Максим.pdf` | **Воробьев М. С. *ИИ-ассистенты на Python*** (Наука и Техника, 2026). Гл. 20 — критерии успеха RAG. В методичке: **[Воробьев]**. |

---

## Репозитории с примерами кода (`D:\BOOK\RAG`)

Клоны на вашем диске; **в репозиторий диплома не входят** — здесь только ссылки на GitHub.

| Локальная папка | Репозиторий | Книга / назначение |
|-----------------|-------------|-------------------|
| `A-Simple-Guide-to-RAG` | [abhinav-kimothi/A-Simple-Guide-to-RAG](https://github.com/abhinav-kimothi/A-Simple-Guide-to-RAG) | Manning, *A Simple Guide to Retrieval Augmented Generation* — вводный курс и примеры RAG |
| `RAG-Driven-Generative-AI_ENG` | [Denis2054/RAG-Driven-Generative-AI](https://github.com/Denis2054/RAG-Driven-Generative-AI) | Rothman, Packt 1-е изд. (ENG): LlamaIndex, Deep Lake, Pinecone |
| `RAG-Driven-Generative-AI` | [webmakaka/RAG-Driven-Generative-AI](https://github.com/webmakaka/RAG-Driven-Generative-AI) | Тот же 1-й том — README и структура под русское издание; upstream — [Denis2054/RAG-Driven-Generative-AI](https://github.com/Denis2054/RAG-Driven-Generative-AI) |
| `RAG-Driven-Generative-AI-2nd-Edition` | [Denis2054/RAG-Driven-Generative-AI-2nd-Edition](https://github.com/Denis2054/RAG-Driven-Generative-AI-2nd-Edition) | Rothman, 2-е изд.: MAS-RAG, DualRAG, GraphRAG, мультимодальные пайплайны |

Связь с PDF в `books/`: `RAG и генеративный ИИ.pdf` и `RAG_и_генеративный_ИИ_Дэнис_Ротман2025.pdf` — к 1-му изданию (строки `RAG-Driven-Generative-AI*`).

---

## Онлайн (если нет локального файла)

- Гл. 8 IR-book: https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html
- DPR: https://arxiv.org/abs/2004.04906
- RAG: https://arxiv.org/abs/2005.11401
