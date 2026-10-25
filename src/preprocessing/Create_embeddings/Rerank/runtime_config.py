# -*- coding: utf-8 -*-
"""Runtime-конфиг опыта 2 (реранкер).

Читает ``rag_runtime_rerank.json`` из этой папки (коллекция ``diplom_multimodal_e5_rerank``).
Базовый ``config/rag_runtime.json`` и ``E5/rag_runtime_e5.json`` не подменяются.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

_RERANK_DIR = Path(__file__).resolve().parent
_BASE_RUNTIME = _RERANK_DIR.parent / "runtime_config.py"

_spec = importlib.util.spec_from_file_location("embeddings_runtime_config_base", _BASE_RUNTIME)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Не найден базовый runtime_config: {_BASE_RUNTIME}")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

RERANK_CONFIG_PATH = _RERANK_DIR / "rag_runtime_rerank.json"
ROOT = _base.ROOT
resolve_repo_path = _base.resolve_repo_path

PROTECTED_COLLECTIONS = frozenset({"diplom_multimodal", "diplom_multimodal_e5"})
RERANK_COLLECTION = "diplom_multimodal_e5_rerank"


def load_runtime_config(config_path: Path | None = None) -> Dict[str, Any]:
    """Как базовый load_runtime_config, но по умолчанию — rag_runtime_rerank.json."""
    return _base.load_runtime_config(config_path or RERANK_CONFIG_PATH)
