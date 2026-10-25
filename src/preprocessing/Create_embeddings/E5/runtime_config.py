# -*- coding: utf-8 -*-
"""Runtime-конфиг опыта E5.

Читает ``rag_runtime_e5.json`` из этой папки (коллекция ``diplom_multimodal_e5``).
Базовый ``config/rag_runtime.json`` и ``Create_embeddings/runtime_config.py`` не подменяются:
общий загрузчик вызывается по пути к файлу и получает другой JSON.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

_E5_DIR = Path(__file__).resolve().parent
_BASE_RUNTIME = _E5_DIR.parent / "runtime_config.py"

_spec = importlib.util.spec_from_file_location("embeddings_runtime_config_base", _BASE_RUNTIME)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Не найден базовый runtime_config: {_BASE_RUNTIME}")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

E5_CONFIG_PATH = _E5_DIR / "rag_runtime_e5.json"
ROOT = _base.ROOT
resolve_repo_path = _base.resolve_repo_path


def load_runtime_config(config_path: Path | None = None) -> Dict[str, Any]:
    """Как базовый load_runtime_config, но по умолчанию — rag_runtime_e5.json."""
    return _base.load_runtime_config(config_path or E5_CONFIG_PATH)
