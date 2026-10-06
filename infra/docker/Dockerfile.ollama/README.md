# Ollama в Docker

Запуск Ollama через Docker для локального использования LLM (NVIDIA GPU).

## Требования

- **NVIDIA GPU** — типовые сценарии диплома:
  - **RTX 2060 (6 ГБ VRAM)** → [рекомендуемые модели](#рекомендуемые-модели-для-rtx-2060-6-гб-vram)
  - **RTX 5060 Ti (16 ГБ VRAM)** → [рекомендуемые модели](#рекомендуемые-модели-для-rtx-5060-ti-16-гб-vram)
- **RAM** 64 ГБ ОЗУ (для комфортной работы хост-системы alongside Docker).
- **NVIDIA Container Toolkit**: [инструкция по установке](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

**Проверка драйверов:**
```bash
# Должна вывести список процессов GPU
nvidia-smi
```

## Быстрый старт

**Автовыбор GPU или CPU** (из корня репозитория):

```powershell
python scripts/compute_detect.py
python scripts/start_ollama.py --pull
```

Скрипт проверяет `nvidia-smi`, PyTorch CUDA и NVIDIA runtime в Docker:
- **GPU** → `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`
- **CPU** → только `docker-compose.yml` (без NVIDIA Container Toolkit)

Ручной запуск:

```bash
cd infra/docker/Dockerfile.ollama
# GPU:
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
# CPU:
docker compose -f docker-compose.yml up -d
```

Модель LLM — в `config/rag_runtime.json` → `ollama.model` (или автовыбор при `model_selection.auto_select_ollama_model` по `config/model_profiles.json` → `ollama_model` в профилях GPU). Рекомендация и запись в конфиг:

```powershell
python scripts/compute_detect.py
python scripts/compute_detect.py --apply-config
python scripts/start_ollama.py --apply-config --pull
```

**Telegram-бот** в этом compose **не поднимается** (заготовка backend закомментирована в `docker-compose.yml` — «логика отдельно»). Актуальный каркас бота: `infra/docker/Dockerfile.bot/` и `src/bot/`.

---

## Рекомендуемые модели для RTX 2060 (6 ГБ VRAM)

| Модель | Размер | Почему подходит | Для чего в дипломе |
|--------|--------|-----------------|--------------------|
| **Llama 3.2 3B** | ~2.0 GB | 🚀 Идеальный баланс. Оставляет ~4 ГБ под контекст. Быстрая генерация. | Основной кандидат для Telegram-бота. |
| **Qwen 2.5 3B** | ~2.0 GB | 🇷🇺 Лучшее понимание русского и технических текстов. | Консультации по ПУЭ, сложные формулировки. |
| **Gemma 2 2B** | ~1.6 GB | Легкая и умная модель от Google. | Быстрые ответы, классификация запросов. |
| **Phi-3 Mini** (3.8B) | ~2.3 GB | 📚 Обучена на технических текстах и документации. | Работа с нормативами и стандартами. |
| **Mistral 7B** (Q3_K_S) | ~4.5 GB | ⚠️ Только если очень нужно. Контекст будет ограничен. | Если 3B не справляется с логикой. |

**Совет:** Начнем с `qwen2.5:3b` или `llama3.2:3b`. Они должны оставить достаточно места в видеопамяти для обработки длинных выдержек из нормативных документов без лагов.

## Рекомендуемые модели для ≥8–12 ГБ VRAM (квантование Q4)

Модели из темы диплома и более мощные варианты — для видеокарт с 8 ГБ VRAM и выше. На 6 ГБ (RTX 2060) **не рекомендуются** без сильного квантования и урезания контекста.

| Модель | Размер (Q4) | Почему подходит | Для чего в дипломе |
|--------|-------------|-----------------|--------------------|
| **Llama 3.1 8B** (`llama3.1:8b`) | ~4.7 GB | 📌 Изначально запланированная модель проекта. Q4 оставляет место под контекст RAG на 8–12 ГБ VRAM. | Основной LLM для генерации ответов по ПУЭ/ПТЭЭП; лучше 3B-моделей по связности и логике. |
| **Llama 3.1 8B Instruct** (`llama3.1:8b-instruct-q4_K_M`) | ~4.9 GB | Явное квантование Q4_K_M — экономия VRAM при сохранении качества instruct-ответов. | Если нужен предсказуемый instruct-режим для RAG-промптов. |
| **Mistral 7B** (Q4) | ~4.1 GB | Хороший баланс качества и скорости на 8 ГБ. | Альтернатива Llama 3.1 8B при нехватке VRAM. |
| **Qwen 2.5 7B** (Q4) | ~4.5 GB | 🇷🇺 Сильнее по русскому языку среди 7B-класса. | Консультации по нормативам со сложными формулировками. |

**Совет:** На **8 ГБ VRAM** начните с `llama3.1:8b` или `llama3.1:8b-instruct-q4_K_M` — это соответствует формулировке темы («Llama 3.1 8B через Ollama»). На **12 ГБ** можно держать более длинный контекст RAG без обрезки чанков.

## Рекомендуемые модели для RTX 5060 Ti (16 ГБ VRAM)

Все модели из таблицы [≥8–12 ГБ VRAM](#рекомендуемые-модели-для-812-гб-vram-квантование-q4) здесь тоже подходят. На **16 ГБ** дополнительно можно брать **14B-класс**, **Q8 для 8B** и **длинный контекст RAG** без постоянного риска OOM (в отличие от RTX 2060).

| Модель | Размер | Почему подходит | Для чего в дипломе |
|--------|--------|-----------------|--------------------|
| **Llama 3.1 8B Instruct** (`llama3.1:8b-instruct-q4_K_M`, `llama3.1:8b`) | ~5–8 GB (Q4–Q8) | 📌 Модель из темы диплома. На 16 ГБ — Q8 или большой контекст под чанки ПУЭ. | Основной LLM для RAG-ответов; предсказуемый instruct-режим. |
| **Qwen 2.5 14B Instruct** (`qwen2.5:14b-instruct-q4_K_M` или `qwen2.5:14b`) | ~9 GB | 🇷🇺 Лучшее качество и русский среди реалистичных для 16 ГБ. Остаётся запас под KV-cache. | Сложные формулировки ПУЭ/ПТЭЭП, связные ответы. |
| **Qwen 2.5 7B** (`qwen2.5:7b`) | ~4.5–6 GB (Q4–Q6) | Быстрее 14B; много свободной VRAM под длинный промпт RAG. | Баланс скорости и качества на защите. |
| **DeepSeek R1 7B** (`deepseek-r1:7b`) | ~4.5 GB | Reasoning с цепочками рассуждений; комфортно на 16 ГБ. | Вопросы, где важна пошаговая логика по нормативам. |
| **DeepSeek R1 14B** (`deepseek-r1:14b`) | ~9 GB | Сильнее 7B по рассуждению; укладывается в 16 ГБ с умеренным контекстом. | Альтернатива Qwen 14B для «умных» ответов. |
| **Gemma 2 9B** (`gemma2:9b`) | ~5.5 GB (Q4) | Альтернатива Llama/Qwen в классе 9B. | Сравнение качества разных семейств моделей. |
| **Llama 3.2 3B / Qwen 2.5 3B** | ~2 GB | Почти не нагружают VRAM — удобны для A/B с 14B на демо. | Быстрые ответы и сравнение с «тяжёлой» основной моделью. |

**Совет:** Для RAG + Telegram на RTX 5060 Ti начните с **`qwen2.5:14b-instruct-q4_K_M`** (качество и русский) или **`llama3.1:8b-instruct-q4_K_M`** (соответствие формулировке темы). Укажите выбранный тег в `config/rag_runtime.json` → `ollama.model`. При авто-выборе embedding-модели на этой карте проект подставляет профиль **`high_gpu`** (`BAAI/bge-m3`) — см. `config/model_profiles.json`.

**Контекст RAG:** на 16 ГБ типично ~10–12 ГБ уходят на веса модели и KV-cache; можно увеличить число чанков в промпте или `num_predict` в `rag_runtime.json` без постоянной нехватки VRAM (на RTX 2060 это обычно невозможно).

### Дополнительные модели (можно добавить)

| Модель | Размер | Особенности |
|--------|--------|-------------|
| **TinyLlama 1.1B** | ~0.6 GB | Самая лёгкая. Максимальная скорость для простых задач. |
| **Llama 3.2 1B** | ~1.0 GB | Минимальная от Meta, хороша для перефразирования. |
| **Qwen 2.5 1.5B** | ~1.0 GB | Компактная версия Qwen с отличным русским языком. |
| **DeepSeek R1 1.5B** | ~1.0 GB | Reasoning-модель с цепочками рассуждений. |
| **SmolLM2 1.7B** | ~1.8 GB | Контекст 8K, мультизадачность. |
| **SmallThinker 3B** | ~3.6 GB | Улучшенный reasoning на базе Qwen 2.5. |
| **CodeLlama 7B** | ~3.8 GB | Специализация на коде (instruct, code, python). |

### Команды для скачивания рекомендуемых моделей

```bash
# Qwen 2.5 3B (лучший для русского языка)
docker exec -it ollama ollama pull qwen2.5:3b

# Llama 3.2 3B (универсальная)
docker exec -it ollama ollama pull llama3.2:3b

# Gemma 2 2B (самая легкая)
docker exec -it ollama ollama pull gemma2:2b

# Phi-3 Mini (для технических текстов)
docker exec -it ollama ollama pull phi3:mini

# --- Дополнительные ---
# TinyLlama (ультралёгкая)
docker exec -it ollama ollama pull tinyllama

# Llama 3.2 1B
docker exec -it ollama ollama pull llama3.2:1b

# Qwen 2.5 1.5B (компактный русский)
docker exec -it ollama ollama pull qwen2.5:1.5b

# SmolLM2 (контекст 8K)
docker exec -it ollama ollama pull smollm2:1.7b

# SmallThinker (reasoning)
docker exec -it ollama ollama pull smallthinker:3b

# CodeLlama (для кода; варианты: 7b-instruct, 7b-code, 7b-python)
docker exec -it ollama ollama pull codellama:7b

# DeepSeek R1 (reasoning, цепочки рассуждений)
docker exec -it ollama ollama pull deepseek-r1:1.5b

# Скачиваем основную модель (инструктивная версия + квантование для экономии VRAM)
docker exec -it ollama ollama pull qwen2.5:3b-instruct-q4_k_m

# --- ≥8–12 ГБ VRAM (квантование Q4) ---
# Llama 3.1 8B — модель из темы диплома (Q4 по умолчанию в Ollama)
docker exec -it ollama ollama pull llama3.1:8b

# Llama 3.1 8B Instruct с явным Q4_K_M
docker exec -it ollama ollama pull llama3.1:8b-instruct-q4_K_M

# Qwen 2.5 7B (русский язык, 7B-класс)
docker exec -it ollama ollama pull qwen2.5:7b

# --- RTX 5060 Ti 16 GB VRAM ---
# Llama 3.1 8B Instruct (модель из темы диплома)
docker exec -it ollama ollama pull llama3.1:8b-instruct-q4_K_M

# Qwen 2.5 14B Instruct (основной кандидат для качества/RU)
docker exec -it ollama ollama pull qwen2.5:14b-instruct-q4_K_M

# Gemma 2 9B
docker exec -it ollama ollama pull gemma2:9b

# DeepSeek R1 (reasoning)
docker exec -it ollama ollama pull deepseek-r1:7b
docker exec -it ollama ollama pull deepseek-r1:14b
```

*Полный каталог моделей: [ollama.com/library](https://ollama.com/library)*

### Сравнение производительности (примерно)

| Модель | Скорость (токенов/сек) | Качество ответов | Потребление VRAM |
|--------|------------------------|------------------|------------------|
| TinyLlama 1.1B | ~60-80 | ⭐⭐ | 0.6 GB |
| Llama 3.2 1B | ~50-65 | ⭐⭐⭐ | 1.0 GB |
| Qwen 2.5 1.5B | ~50-65 | ⭐⭐⭐⭐ (для RU) | 1.0 GB |
| DeepSeek R1 1.5B | ~45-55 | ⭐⭐⭐⭐ (reasoning) | 1.0 GB |
| Gemma 2 2B | ~40-50 | ⭐⭐⭐ | 1.6 GB |
| SmolLM2 1.7B | ~40-50 | ⭐⭐⭐ | 1.8 GB |
| Llama 3.2 3B | ~30-40 | ⭐⭐⭐⭐ | 2.0 GB |
| Qwen 2.5 3B | ~30-40 | ⭐⭐⭐⭐⭐ (для RU) | 2.0 GB |
| Phi-3 Mini | ~25-35 | ⭐⭐⭐⭐ (для тех. текстов) | 2.3 GB |
| SmallThinker 3B | ~25-35 | ⭐⭐⭐⭐ (reasoning) | 3.6 GB |
| CodeLlama 7B | ~18-25 | ⭐⭐⭐⭐⭐ (код) | 3.8 GB |
| Mistral 7B (Q3) | ~15-20 | ⭐⭐⭐⭐⭐ | 4.5 GB |
| Llama 3.1 8B (Q4) | ~12-18 | ⭐⭐⭐⭐⭐ | ~4.7 GB (8–12 ГБ VRAM) |
| Llama 3.1 8B Instruct (Q4_K_M) | ~12-18 | ⭐⭐⭐⭐⭐ (instruct/RAG) | ~4.9 GB (8–12 ГБ VRAM) |
| Qwen 2.5 7B (Q4) | ~15-22 | ⭐⭐⭐⭐⭐ (для RU) | ~4.5 GB (8–12 ГБ VRAM) |
| Llama 3.1 8B Instruct (Q8) | ~18-28 | ⭐⭐⭐⭐⭐ (instruct/RAG) | ~8 GB (RTX 5060 Ti 16 ГБ) |
| Qwen 2.5 14B (Q4_K_M) | ~10-16 | ⭐⭐⭐⭐⭐ (для RU) | ~9 GB (RTX 5060 Ti 16 ГБ) |
| DeepSeek R1 14B (Q4) | ~8-14 | ⭐⭐⭐⭐⭐ (reasoning) | ~9 GB (RTX 5060 Ti 16 ГБ) |
| Gemma 2 9B (Q4) | ~14-22 | ⭐⭐⭐⭐ | ~5.5 GB (RTX 5060 Ti 16 ГБ) |

*Скорость: строки до Mistral 7B (Q3) — ориентир для **RTX 2060 (6 ГБ)**; Llama 3.1 8B и Qwen 2.5 7B (Q4) — для **8–12 ГБ VRAM**; строки Q8 / 14B / Gemma 9B — для **RTX 5060 Ti (16 ГБ)**. Реальные значения зависят от длины контекста.*

## Использование

### API
- **Адрес**: `http://localhost:11434`

### Принцип работы (Библиотека моделей)
Ollama устроена как «библиотека»: вы можете скачать сколько угодно моделей (они хранятся на диске и не потребляют ресурсы), но **одновременно активна обычно только одна** (загружается в VRAM).
- **Диск:** Можно хранить 5–10 моделей для тестов (~10–20 ГБ).
- **VRAM:** При переключении модели (например, с `llama3.2:3b` на `qwen2.5:7b`) происходит выгрузка одной и загрузка другой (занимает 10–30 секунд).

### Управление моделями

| Команда | Что делает | Пример |
|---------|------------|--------|
| `ollama pull <model>` | Скачивает модель в хранилище | `docker exec -it ollama ollama pull qwen2.5:3b` |
| `ollama run <model>` | Запускает интерактивный чат с моделью | `docker exec -it ollama ollama run llama3.2:3b` |
| `ollama list` | Показывает список скачанных моделей | `docker exec -it ollama ollama list` |
| `ollama rm <model>` | Удаляет модель (освобождает место) | `docker exec -it ollama ollama rm mistral` |

> **Важно:** Команда `ollama run` — это **интерактивный режим** (чат в терминале) для ручного тестирования. Бот общается с моделями **через API**, а не через `run`.

**Пример диалога:**
```bash
# 1. Скачали несколько моделей
docker exec -it ollama ollama pull llama3.2:3b
docker exec -it ollama ollama pull qwen2.5:3b
docker exec -it ollama ollama pull gemma2:2b

# 2. Посмотрели, что есть
docker exec -it ollama ollama list
# NAME             SIZE
# llama3.2:3b      2.0GB
# qwen2.5:3b       2.1GB
# gemma2:2b        1.6GB

# 3. Запустили чат с любой из списка
docker exec -it ollama ollama run qwen2.5:3b
>>> Привет, какие требования к заземлению в ПУЭ?
```

**Скачать модель:**
```bash
docker exec -it ollama ollama pull llama3.2:3b
```

**Запустить чат:**
```bash
docker exec -it ollama ollama run llama3.2:3b
```

**Список доступных моделей:** https://ollama.com/library

## Нюансы для RTX 2060 (6 ГБ VRAM)

| Ресурс | Особенности |
|--------|-------------|
| **Диск (хранение)** | Можно скачать 5–10 моделей для тестов. 5 моделей по ~2 ГБ ≈ 10 ГБ на диске — это нормально. |
| **Видеопамять (VRAM)** | Одновременно активна обычно **одна** модель. При переключении с `llama3.2:3b` на `qwen2.5:7b` Ollama выгрузит первую и загрузит вторую (10–30 сек). **Совет:** выберите одну основную модель (например, `qwen2.5:3b`) и работайте с ней. Остальные держите для сравнения качества. |
|**Совет для демонстрации:** |Для диплома выберите одну основную модель (например, `qwen2.5:3b`) и работайте с ней во время показа. Переключение моделей занимает время (10–30 сек), что может создать паузы в демо. Остальные модели держите «про запас» для сравнения качества в коде.|
**Итог:** Качайте модели через `pull`, тестируйте через `run`, в коде бота меняйте `"model": "name"` в JSON-запросе.

## Нюансы для RTX 5060 Ti (16 ГБ VRAM)

| Ресурс | Особенности |
|--------|-------------|
| **Диск (хранение)** | Как на 2060: 5–10 моделей для тестов (~20–40 ГБ на диске, если держать 8B + 14B + лёгкие 3B). |
| **Видеопамять (VRAM)** | Одновременно активна обычно **одна** модель. Переключение `llama3.1:8b-instruct-q4_K_M` ↔ `qwen2.5:14b-instruct-q4_K_M` — те же 10–30 сек. Можно пробовать **Q8** для 8B без угрозы OOM (на 2060 неактуально). |
| **Совет для демонстрации** | Основная модель для показа — **14B instruct** или **8B instruct**; `qwen2.5:3b` / `llama3.2:3b` оставьте для сравнения скорости. Длинный RAG-контекст на защите безопаснее, чем на 6 ГБ. |

**Итог:** Укажите основную модель в `rag_runtime.json`; embedding для этой карты — профиль `high_gpu` (`bge-m3`) при включённом авто-выборе.

## Мониторинг ресурсов

**Linux/Mac:**
```bash
# В отдельном терминале
watch -n 1 nvidia-smi
```

**Windows PowerShell:**
```powershell
# Вариант 1: Цикл с обновлением каждую секунду
while ($true) { cls; nvidia-smi; Start-Sleep -Seconds 1 }

# Вариант 2: Однократный просмотр
nvidia-smi

# Вариант 3: Логи Docker
docker logs -f ollama
```

## Интеграция с проектом (RAG + Бот)

### Адреса подключения:
- **Бот на хосте**: `http://localhost:11434`
- **Бот в Docker Compose**: `http://ollama:11434`

### Как бот выбирает модель?

Бот отправляет HTTP-запрос на порт `11434` и указывает имя модели в параметре `model`. Можно сделать команду `/model` в боте, чтобы переключать ИИ-модель на лету без перезапуска.

### Пример кода (синхронный)

```python
import os
import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def ask_llm(prompt: str, model: str = "llama3.2:3b"):
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}
    )
    return response.json()["response"]

# Использование:
print(ask_llm("Что такое заземление?", "llama3.2:3b"))
print(ask_llm("Нормы заземления по ПУЭ?", "qwen2.5:3b"))  # Другая модель!
```

### Пример кода (асинхронный)

```python
import os
import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

async def ask_llm_async(prompt: str, model: str = "llama3.2:3b"):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        return response.json()["response"]
```

### Правильный промпт для ПУЭ (системный промпт)

Для нормативных документов важно «заземлить» модель. Передавайте этот системный промпт:

```python
SYSTEM_PROMPT = """
Ты — эксперт-консультант по электротехнике. Твоя задача — отвечать на вопросы строго на основе предоставленных фрагментов из ПУЭ, ПТЭЭП и ГОСТ.

ПРАВИЛА:
1. Если ответа нет в контексте — напиши "В предоставленных документах нет информации". Не выдумывай.
2. Обязательно указывай номер пункта или главы (например: "согласно п. 1.7.102 ПУЭ").
3. Отвечай кратко, профессиональным языком, без "воды".
4. Язык ответа: русский.
"""
или

SYSTEM_PROMPT = """
Ты — эксперт-консультант по электротехнике. Твоя задача — отвечать на вопросы строго на основе предоставленных фрагментов из ПУЭ, ПТЭЭП и ГОСТ.
Отвечай строго на основе предоставленных фрагментов. 
Если ответа нет в контексте — напиши "В предоставленных документах нет информации".
Обязательно указывай номер пункта ПУЭ.
"""
```

### Пример промпта с контекстом (RAG)
Именно в таком формате бот должен отправлять запрос к модели (системная инструкция + найденный фрагмент + вопрос):

```text
Контекст из ПУЭ п. 1.7.102: "В электроустановках до 1 кВ применяется система TN-C-S..."
Вопрос: Что такое система TN-C-S?
Ответь строго по контексту, укажи номер пункта.
```


### Фишка для диплома: Команда `/model`
Рекомендуется реализовать в боте команду `/model`, чтобы переключать ИИ-модель на лету без перезапуска бота.
**Пример использования:**
- `/model qwen2.5:3b` — переключить на лучшую для русского языка (RTX 2060).
- `/model llama3.2:3b` — переключить на универсальную (RTX 2060).
- `/model qwen2.5:14b-instruct-q4_K_M` — основная модель для RTX 5060 Ti (качество/RU).
- `/model llama3.1:8b-instruct-q4_K_M` — модель из темы диплома на 16 ГБ VRAM.
Это позволит демонстрировать работу разных моделей во время защиты.

## Практическая настройка под ПУЭ

Для точных ответов по нормативам важны не только модель, но и параметры запуска.

### 1. Скачивание и проверка

```bash
# Скачиваем основную модель (инструктивная версия + квантование)
docker exec -it ollama ollama pull qwen2.5:3b-instruct-q4_k_m

# Тестовый запрос на знание терминологии
docker exec -it ollama ollama run qwen2.5:3b "Что такое система TN-C-S согласно ПУЭ?"

docker exec -it ollama ollama run llama3.2:3b "Что такое система TN-C-S согласно ПУЭ (Правила устройств электроустановок)? Ответьте не придумывая!!!!"

docker exec -it ollama ollama run gemma2:2b "Что такое система TN-C-S согласно ПУЭ (Правила устройств электроустановок)? Ответь строго по контексту, укажи номер пункта."
```

### 2. Проверка качества ответов

После скачивания модели протестируйте её на типичных вопросах:

```bash
# Запустите интерактивный чат
docker exec -it ollama ollama run qwen2.5:3b

# Примеры тестовых вопросов:
>>> Какие требования к заземлению в электроустановках до 1000В?
>>> Что такое защитное заземление по ПУЭ?
>>> Какие системы заземления существуют?
```

---

## Полезные команды Docker

```bash
# Остановить контейнер
docker compose down

# Посмотреть логи (если что-то не работает)
docker compose logs -f ollama
# или docker logs -f ollama

# Перезапустить после обновления образа
docker compose pull && docker compose up -d

# Освободить VRAM вручную (модели выгружаются автоматически через ~5 мин простоя)
docker restart ollama
```

## Проверка работы

```bash
# Быстрый тест API (должен вернуть список моделей)
curl http://localhost:11434/api/tags

# Или простой запрос
curl http://localhost:11434/api/generate -d '{"model":"llama3.2:3b","prompt":"Привет","stream":false}'
```

## Переменные окружения (опционально)

Можно добавить в `docker-compose.yml` под `environment:` для тонкой настройки:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `OLLAMA_NUM_GPU` | Сколько GPU использовать | `1` |
| `OLLAMA_MAX_LOADED_MODELS` | Макс. моделей в памяти | `2` |
| `OLLAMA_KEEP_ALIVE` | Как долго держать модель в памяти | `5m` |

## Стриминг (для длинных ответов)

Для бота с постепенной печатью ответа использовать `stream: true` и читать ответ по частям:

```python
import json
import os
import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
response = requests.post(
    f"{OLLAMA_HOST}/api/generate",
    json={"model": "llama3.2:3b", "prompt": prompt, "stream": True},
    stream=True
)
for line in response.iter_lines():
    if line:
        chunk = json.loads(line)
        if "response" in chunk:
            print(chunk["response"], end="", flush=True)
```

## Документация API

- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) — полный список эндпоинтов
- `/api/generate` — генерация текста
- `/api/chat` — диалог с историей сообщений