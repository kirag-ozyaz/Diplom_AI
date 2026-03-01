Ниже представлен оптимизированный **`docker-compose.yml`** для запуска **Milvus Standalone** (версия 2.4.x) вместе с интерфейсом **Attu** для управления данными.

Эта конфигурация адаптирована под вашу задачу: она использует облегченный режим очередей (RockMQ), чтобы не перегружать систему лишними сервисами, и выделяет достаточный объем памяти для комфортной работы с векторами.

### 1. Файл `docker-compose.yml`

Создайте папку для проекта, а в ней файл `docker-compose.yml` и вставьте следующий код:

```yaml
version: '3.5'

services:
  etcd:
    container_name: milvus-etcd
    image: quay.io/coreos/etcd:v3.5.5
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
      - ETCD_SNAPSHOT_COUNT=50000
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/etcd:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    healthcheck:
      test: ["CMD", "etcdctl", "endpoint", "health"]
      interval: 30s
      timeout: 20s
      retries: 3
    networks:
      - milvus
    restart: always

  minio:
    container_name: milvus-minio
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9001:9001"
      - "9000:9000"
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/minio:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    networks:
      - milvus
    restart: always

  milvus-standalone:
    container_name: milvus-standalone
    image: milvusdb/milvus:v2.4.6
    command: ["milvus", "run", "standalone"]
    security_opt:
    - seccomp:unconfined
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      # Оптимизация памяти для 64GB RAM
      QUERY_NODE_CACHE_MEMORY_LIMIT: 16
      ROCKSMQ_RETENTION_TIME_IN_MINUTES: 10080
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/milvus:/var/lib/milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - "etcd"
      - "minio"
    networks:
      - milvus
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      start_period: 90s
      timeout: 20s
      retries: 3

  attu:
    container_name: milvus-attu
    image: zilliz/attu:v2.4.0
    environment:
      MILVUS_URL: http://milvus-standalone:19530
    ports:
      - "3000:3000"
    depends_on:
      - "milvus-standalone"
    networks:
      - milvus
    restart: always

networks:
  milvus:
    driver: bridge
```

### 2. Инструкция по запуску

1.  **Создать структуру папок:**
    Убедиться, что у вас есть права на создание папки `volumes` в текущей директории (Milvus создаст её автоматически для хранения данных).
2.  **Запустить контейнеры:**
    Открыть терминал в папке с файлом и выполнить:
    ```bash
    docker-compose up -d
    ```
3.  **Проверка статуса:**
    Milvus загружается дольше обычных сервисов (из-за инициализации компонентов). Проверить логи:
    ```bash
    docker-compose ps
    docker-compose logs -f milvus-standalone
    ```
    *Ожидать появления сообщения `Welcome to Milvus!`.*
4.  **Доступ к интерфейсу (Attu):**
    Открыть в браузере: `http://localhost:3000`
    *   **Milvus Address:** `http://milvus-standalone:19530` (если спросит при подключении внутри сети Docker) или просто оставить по умолчанию, если подключаетесь снаружи.

### 3. Конфигурация для Python (подключение)

Для работы с базой из кода (загрузка JSONL) используйте следующие параметры:

```python
from pymilvus import connections

# Подключение к локальному Milvus
connections.connect(
    alias="default",
    host="localhost",
    port="19530"
)

print("Успешное подключение к Milvus!")
```

### 4. Пояснение к настройкам (для диплома)

В конфигурации учтены следующие моменты, которые можно описать в пояснительной записке:

| Параметр | Значение | Обоснование для диплома |
| :--- | :--- | :--- |
| **Режим** | `standalone` | Оптимально для одного сервера, снижает накладные расходы на сеть по сравнению с кластером. |
| **Очереди** | `RockMQ` (по умолчанию в v2.4) | В версии 2.4.x используется легковесная очередь на базе RocksDB вместо тяжелого Apache Pulsar, что экономит ~2-4 ГБ ОЗУ. |
| **Cache Limit** | `16` (GB) | Выделено 16 ГБ под кэш поисковых узлов. С вашими 64 ГБ это безопасный лимит, обеспечивающий быстрый поиск. |
| **Хранилище** | `MinIO` | Объектное хранилище для persistence данных (симуляция S3), стандарт для микросервисной архитектуры. |
| **Метаданные** | `etcd` | Распределенное хранилище ключ-значение для управления метаданными кластера. |

### 5. Полезные команды для управления

```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением данных (полный сброс)
docker-compose down -v

# Просмотр логов Milvus
docker-compose logs -f milvus-standalone

# Перезапуск конкретного сервиса
docker-compose restart milvus-standalone
```

### 6. Ресурсы

*   **Milvus** займет около **4–8 ГБ** в простое.
*   **Attu** займет около **500 МБ**.
*   **Остаток (~55 ГБ)** доступен для  **LLM** и **Embedding-моделей** на видеокарте и в системе.

