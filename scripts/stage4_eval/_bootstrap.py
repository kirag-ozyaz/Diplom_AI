# -*- coding: utf-8 -*-
"""Корень репо и sys.path для скриптов stage4_eval."""
from __future__ import annotations

import sys
from pathlib import Path

STAGE4_EVAL = Path(__file__).resolve().parent
SCRIPTS = STAGE4_EVAL.parent
ROOT = SCRIPTS.parent


def setup_paths(*, embed: bool = False) -> Path:
    """Добавляет ROOT, scripts/, stage4_eval/ в sys.path. embed=True — Create_embeddings."""
    for p in (ROOT, SCRIPTS, STAGE4_EVAL):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    if embed:
        embed_dir = ROOT / "src" / "preprocessing" / "Create_embeddings"
        s = str(embed_dir)
        if s not in sys.path:
            sys.path.insert(0, s)
    return ROOT
