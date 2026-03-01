1. Запуск контейнера
docker-compose up -d

2. Проверка статуса

docker-compose ps
docker-compose logs -f milvus-standalone

3. # Остановка всех сервисов
docker-compose down

# Остановка с удалением данных (полный сброс)
docker-compose down -v

# Просмотр логов Milvus
docker-compose logs -f milvus-standalone

# Перезапуск конкретного сервиса
docker-compose restart milvus-standalone

# Запуск заново (флаг -d для фона)
docker-compose up -d