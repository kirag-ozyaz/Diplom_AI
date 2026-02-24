https://milvus.io/docs/ru/quickstart.md
https://milvus.io/docs/ru/install_standalone-windows.md

### 0. Установить Milvus

# Download the configuration file and rename it as docker-compose.yml
C:\>Invoke-WebRequest https://github.com/milvus-io/milvus/releases/download/v2.6.11/milvus-standalone-docker-compose.yml -OutFile docker-compose.yml

# Start Milvus
C:\>docker compose up -d

Отличные новости! 🎉 Все основные сервисы Milvus успешно запущены и работают в здоровом состоянии (status: **healthy**).

Однако я заметил важный нюанс: в списке запущенных контейнеров **отсутствует Attu** (веб-интерфейс для управления). Скорее всего, вы скачали официальный шаблон с GitHub, в котором по умолчанию нет интерфейса, а использовали мой конфиг с Attu.

Вот следующие шаги для полной готовности системы:

### 1. Как запустить интерфейс (Attu)
Чтобы визуально просматривать данные (), нужно запустить Attu отдельно. Так как основные сервисы уже работают, просто добавьте интерфейс:

```powershell
docker run -d --name milvus-attu -p 3000:3000 -e MILVUS_URL=http://milvus-standalone:19530 --network milvus zilliz/attu:v2.4.0
```
*Примечание: Если сеть `milvus` не найдется, попробуйте запустить без `--network`, но тогда в переменной `MILVUS_URL` укажите `host.docker.internal:19530`.*

После запуска откройте в браузере: **`http://localhost:3000`**

### 2. Проверка подключения через Python
Прежде чем загружать данные, убедитесь, что Python видит базу. Установите клиент, если еще нет:
```powershell
pip install pymilvus
```

Создайте файл `test_connection.py` и запустите:
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



### 5. Следующие шаги для RAG
Теперь инфраструктура готова. Ваш план работы:
1.  **Подготовка:** Напишите скрипт загрузки JSONL (эмбеддинги + векторы).
2.  **Индексация:** Загрузите чанки в коллекцию Milvus.
3.  **Тест:** Выполните поисковый запрос через Python и сверьте результат в Attu.
4.  **Интеграция:** Подключите LLM для генерации ответа.

Инфраструктурная часть диплома готова! Можно переходить к коду.