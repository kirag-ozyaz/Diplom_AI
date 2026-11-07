# -*- coding: utf-8 -*-
"""Корневой каталог проекта и настройка sys.path для скриптов оценки этапа 4."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_console_utf8_done = False

LIB = Path(__file__).resolve().parent
STAGE4_EVAL = LIB.parent
SCRIPTS = STAGE4_EVAL.parent
ROOT = SCRIPTS.parent


def ensure_utf8_console() -> None:
    """Русский текст в cmd / PowerShell на Windows (UTF-8)."""
    global _console_utf8_done
    if _console_utf8_done:
        return
    _console_utf8_done = True
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except (AttributeError, OSError):
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def setup_paths(*, embed: bool = False) -> Path:
    """Добавляет ROOT, scripts/, stage4_eval/ в sys.path. embed=True — Create_embeddings."""
    ensure_utf8_console()
    scripts_lib = SCRIPTS / "lib"
    stage4_paths = (
        LIB,
        STAGE4_EVAL,
        STAGE4_EVAL / "retrieval",
        STAGE4_EVAL / "generation",
        STAGE4_EVAL / "reports",
        STAGE4_EVAL / "demo",
    )
    for p in (ROOT, SCRIPTS, scripts_lib, *stage4_paths):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    if embed:
        embed_dir = ROOT / "src" / "preprocessing" / "Create_embeddings"
        s = str(embed_dir)
        if s not in sys.path:
            sys.path.insert(0, s)
    return ROOT
