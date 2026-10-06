# -*- coding: utf-8 -*-
"""Загрузка runtime-конфига RAG из файла config/rag_runtime.json.

Где что настраивать
-------------------
**Обычно правьте только** ``config/rag_runtime.json`` (Milvus, пути, embedding, Ollama, load_data, query).

**``DEFAULT_RUNTIME_CONFIG`` ниже** — запасные значения в коде (fallback). Их не нужно менять под каждую машину,
если JSON уже есть в репозитории.

Как собирается итоговый конфиг
------------------------------
``load_runtime_config()``:

1. Берёт ``DEFAULT_RUNTIME_CONFIG`` как базу.
2. Поверх накладывает ``config/rag_runtime.json`` (рекурсивный merge по секциям).
3. Если JSON отсутствует или повреждён — возвращается только ``DEFAULT_RUNTIME_CONFIG``.

Ключ из JSON **перекрывает** тот же ключ из дефолта. Отсутствующие в JSON ключи **остаются** из дефолта
(удобно при добавлении новых полей в код без немедленного обновления JSON).

Исключения
----------
- ``OllamaClient``: переменная окружения ``OLLAMA_HOST`` перебивает ``ollama.host`` из конфига.
- ``multimodal_rag.resolve_torch_device``: при ``device_text: cuda`` без CUDA в PyTorch — fallback на ``cpu``.
- Автовыбор embedding-модели: ``model_selector.py`` + ``config/model_profiles.json`` при
  ``model_selection.auto_select_text_model: true``.
- Автовыбор LLM Ollama: ``select_ollama_model`` + поле ``ollama_model`` в профилях при
  ``model_selection.auto_select_ollama_model: true``.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT / "config" / "rag_runtime.json"

# Fallback-значения (см. docstring модуля). Рабочая копия настроек — config/rag_runtime.json.
DEFAULT_RUNTIME_CONFIG: Dict[str, Any] = {    "vector_db": {
        "host": "localhost",
        "port": "19530",
        "collection_name": "diplom_multimodal",
    },
    "paths": {
        "base_data_path": "data",
        "chunked_path": "data/chunked",
    },
    "models": {
        "text_model_name": "intfloat/multilingual-e5-base",
        "clip_model_name": "ViT-B-32",
        "device_text": "cuda",
        "device_clip": "cpu",
    },
    "model_selection": {
        "auto_select_text_model": True,
        "auto_select_ollama_model": True,
    },
    "load_data": {
        "drop_existing": True,
        "use_async": True,
        "batch_size": 32,
        "skip_existing": False,
        "log_every_batches": 1,
        "log_file_summary": True,
    },
    "query": {
        "default_limit": 5,
    },
    "query_test": {
        "search_text": "# Нулевой защитный и нулевой рабочий проводники",
        "limit": 10,
    },
    "ollama": {
        "host": "http://localhost:11434",
        "model": "qwen2.5:3b",
        "timeout_sec": 120,
        "temperature": 0.2,
        "num_predict": 512,
    },
}


def _merge_dicts(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Рекурсивно объединяет словари, сохраняя значения base по умолчанию."""
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_runtime_config(config_path: Path | None = None) -> Dict[str, Any]:
    """
    Загружает runtime-конфиг RAG: merge(DEFAULT_RUNTIME_CONFIG, rag_runtime.json).

    Args:
        config_path: путь к JSON; по умолчанию config/rag_runtime.json от корня репозитория.

    Returns:
        Словарь с итоговыми параметрами для load_data, query, rag_service, ollama_client и т.д.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return dict(DEFAULT_RUNTIME_CONFIG)

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if not isinstance(raw, dict):
                return dict(DEFAULT_RUNTIME_CONFIG)
            return _merge_dicts(DEFAULT_RUNTIME_CONFIG, raw)
    except (OSError, json.JSONDecodeError, TypeError):
        return dict(DEFAULT_RUNTIME_CONFIG)


def resolve_repo_path(path_value: str) -> Path:
    """Преобразует путь из конфига в абсолютный путь относительно корня репозитория."""
    path_obj = Path(path_value)
    if path_obj.is_absolute():
        return path_obj
    return (ROOT / path_obj).resolve()
