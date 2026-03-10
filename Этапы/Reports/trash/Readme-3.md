Этап №3. | AI/ML | Парсинг данных

1. Перевел все файлы *.docx  "ПРАВИЛА УСТРОЙСТВА ЭЛЕКТРОУСТАНОВОК" в файлы формата Markdown
[https://github.com/kirag-ozyaz/Diplom_AI/tree/main/data/extracted]

Была сделана обработка конвертации файлов *.docx в *.md, картинки (изображения), которые присутствовали в файлах, выгрузил в отдельные папки — так проще связывать их с текстом в чанках.

Обработку делал с помощью следующих скриптов:
https://github.com/kirag-ozyaz/Diplom_AI/blob/main/src/preprocessing/Create_mds/docx_to_md_images_1.py (обработка одного файла)
https://github.com/kirag-ozyaz/Diplom_AI/blob/main/src/preprocessing/Create_mds/generator.py (массовая обработка)


2. Отредактировал файлы *.md "ПРАВИЛА УСТРОЙСТВА ЭЛЕКТРОУСТАНОВОК" (глава 1, для отработки пайплайна).
Убрал повторяющиеся картинки, выделил формулы и таблицы (думаю, что потом смогу их нормально отображать).

3. Перевел файлы *.md в чанки *.jsonl  (JSON Lines) 

В качестве чанка выбрал пункты в файлах согласно шаблону (X.Y.Z). Изображения оставлял внутри чанков. Такое разбиение подходит для векторного поиска по релевантным фрагментам.

Готовые файлы лежат в [https://github.com/kirag-ozyaz/Diplom_AI/tree/main/data/chunked]

Обработку делал с помощью следующих скриптов:
https://github.com/kirag-ozyaz/Diplom_AI/blob/main/src/preprocessing/Create_chunkeds/md_to_chunked_2 (обработка одного файла)
https://github.com/kirag-ozyaz/Diplom_AI/blob/main/src/preprocessing/Create_chunkeds/generator.py (массовая обработка)


4. В качестве векторной базы данных выбрал Milvus
Структуру docker-compose создал в отдельной папке [https://github.com/kirag-ozyaz/Diplom_AI/tree/main/infra]

Для визуального просмотра данных поднял через Docker интерфейс Attu — по нему проверяю, что данные в коллекциях загружены корректно.

5. Загрузил заранее подготовленные чанки в локальную базу данных

Отдельно сделал загрузку текста и картинок (картинки буду выбирать через CLIP — надо попробовать, вдруг зайдёт). Эмбеддинги текста считаются при загрузке.

Загрузку делал с помощью следующих скриптов:

https://github.com/kirag-ozyaz/Diplom_AI/blob/799d24514006869dfffd1121d60e16c25872613f/src/preprocessing/Create_embeddings/load_data.py (Скрипт загрузки данных)
https://github.com/kirag-ozyaz/Diplom_AI/blob/799d24514006869dfffd1121d60e16c25872613f/src/preprocessing/Create_embeddings/multimodal_rag.py (Класс для управления загрузкой и выгрузкой данных)

https://github.com/kirag-ozyaz/Diplom_AI/blob/799d24514006869dfffd1121d60e16c25872613f/src/preprocessing/Create_embeddings/query_test.py (тестирование запросов)

Данные в векторной БД, тестовые запросы проверяются; дальше — доработка RAG и поиск по картинкам (CLIP).