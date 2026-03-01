https://milvus.io/docs/ru/quickstart.md
https://milvus.io/docs/ru/install_standalone-windows.md

### 0. Установка Milvus

# Download the configuration file and rename it as docker-compose.yml
C:\>Invoke-WebRequest https://github.com/milvus-io/milvus/releases/download/v2.6.11/milvus-standalone-docker-compose.yml -OutFile docker-compose.yml

# Start Milvus
C:\>docker compose up -d

Отличные новости! 🎉 Все основные сервисы Milvus успешно запущены и работают в здоровом состоянии (status: **healthy**).

Однако я заметил важный нюанс: в списке запущенных контейнеров **отсутствует Attu** (веб-интерфейс для управления). Скорее всего, вы скачали официальный шаблон с GitHub, в котором по умолчанию нет интерфейса, а использовали мой конфиг с Attu.

Вот следующие шаги для полной готовности системы:

### 1. Как запуск интерфейс (Attu)
Чтобы визуально просматривать данные (), нужно запустить Attu отдельно. Так как основные сервисы уже работают, просто добавить интерфейс:

```powershell
docker run -d --name milvus-attu -p 3000:3000 -e MILVUS_URL=http://milvus-standalone:19530 --network milvus zilliz/attu:v2.4.0
```
*Примечание: Если сеть `milvus` не найдется, попробуйте запустить без `--network`, но тогда в переменной `MILVUS_URL` укажите `host.docker.internal:19530`.*

После запуска откройте в браузере: **`http://localhost:3000`**

**Переподключить Attu к новой базе (после docker-compose down / up):**  
Сеть и контейнер Milvus пересоздаются, старый контейнер Attu может остаться без сети. Удалите старый Attu и запустите заново (из каталога `infra/milvus`, после того как `docker-compose up -d` уже выполнен):

```powershell
docker rm -f milvus-attu 2>$null; docker run -d --name milvus-attu -p 3000:3000 -e MILVUS_URL=http://milvus-standalone:19530 --network milvus zilliz/attu:v2.4.0
```

Откройте **http://localhost:3000** — Attu подключится к текущему Milvus (в т.ч. к базе на SSD).

### 2. Проверка подключения через Python
Прежде чем загружать данные, убедиться, что Python видит базу. Установить клиент, если еще нет:
```powershell
pip install pymilvus
```

Создать файл `test_connection.py` и запустить:
```python
from pymilvus import connections, utility

try:
    # Подключение к локальному Milvus
    connections.connect(host="localhost", port="19530")
    print("✅ Успешное подключение к Milvus!")
    
    # Проверка списка коллекций
    collections = utility.list_collections()
    print(f"📦 Существующие коллекции: {collections}")
    
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
```

--

### 6. Хранение данных на SSD и полная пересборка БД

**Перенос данных на другой диск (SSD)**

Тома Docker (etcd, minio, milvus) задаются переменной `DOCKER_VOLUME_DIRECTORY`. По умолчанию они создаются в текущей папке (`./volumes/`).

Чтобы хранить БД на SSD:

1. В каталоге `infra/milvus/` скопировать пример конфига:  
   `copy .env.example .env`
2. Открыть `.env` и задать путь на SSD, например:  
   `DOCKER_VOLUME_DIRECTORY=D:/milvus_data`  
   (или `E:/milvus_volumes` — использовать свой букву диска и путь).
3. При следующем запуске `docker-compose up -d` тома будут созданы уже на SSD.  
   Если контейнеры уже были запущены с старым путём, сначала выполнить шаги из «Полная пересборка БД» ниже.

**Полная пересборка БД (удаление старой БД и создание новой на SSD)**

1. Перейти в каталог с `docker-compose.yml`:  
   `cd infra/milvus`
2. Остановить контейнеры и **удалить тома** (вся база будет удалена):  
   `docker-compose down -v`
3. (Опционально) Задать путь на SSD в `.env`, как в пункте 6 выше.
4. Запустить заново:  
   `docker-compose up -d`
5. Дождаться готовности Milvus (проверка: `query_test.py` или порт 19530).
6. Заново проиндексировать данные:  
   `python src/preprocessing/Create_embeddings/load_data.py`  
   (из корня проекта или из папки `Create_embeddings`).

После этого база будет пустая и расположена на выбранном диске (в т.ч. SSD).

**Если папка на диске (например, `c:/milvus_volumes`) остаётся пустой**

1. **Используется именно `.env`** — Docker Compose подхватывает только файл с именем `.env` в папке с `docker-compose.yml`. Если вы правили только `.env.example`, скопировать его в `.env`:  
   `copy .env.example .env`  
   и в `.env` задать `DOCKER_VOLUME_DIRECTORY=c:/milvus_volumes` (или свой путь).

2. **Docker Desktop (Windows):** для монтирования диска он должен быть в списке «File sharing».  
   Открыть **Docker Desktop → Settings → Resources → File sharing** и добавить при необходимости диск (например, `C:\`) или использовать путь внутри профиля, который уже расшарен:  
   `C:/Users/<ваш_логин>/milvus_volumes`.

3. После изменения `.env` перезапустить с пересозданием томов:  
   `docker-compose down -v`  
   `docker-compose up -d`  
   будет следующая структура на диске: `c:/milvus_volumes/volumes/etcd`, `.../volumes/minio`, `.../volumes/milvus` — каталоги создаются при первом запуске контейнеров.