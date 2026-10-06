# Dockerfile для Telegram-бота (RAG + Ollama)
# Сборка из корня проекта: docker build -f infra/docker/Dockerfile.bot/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

# Системные зависимости (для sentence-transformers, torch и др.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Telegram Bot API (aiogram — асинхронный фреймворк)
RUN pip install --no-cache-dir aiogram>=3.0

# Исходный код
COPY src/ ./src/

# Переменные окружения (переопределяются через docker-compose / -e)
ENV PYTHONPATH=/app
ENV OLLAMA_HOST=http://ollama:11434
ENV MILVUS_HOST=milvus-standalone
ENV MILVUS_PORT=19530
ENV COLLECTION_NAME=diplom_multimodal

# Токен бота задаётся при запуске: -e TG_BOT_TOKEN=...
# CMD переопределяется при наличии src.bot
CMD ["python", "-m", "src.bot"]
