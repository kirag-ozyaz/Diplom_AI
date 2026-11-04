"""Подготовка окружения для отчётных ноутбуков (Readme-3, Readme-4 и др.)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict


class NotebookEnv(TypedDict):
    ROOT: Path
    REPORTS: Path
    EMBED_DIR: Path


def find_project_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "config" / "rag_runtime.json").is_file() and (
            candidate / "src" / "preprocessing"
        ).is_dir():
            return candidate
    raise FileNotFoundError(
        "Корень проекта не найден. Откройте ноутбук из Этапы/Reports или корня репозитория."
    )


def bootstrap(start: Path | None = None) -> NotebookEnv:
    root = find_project_root(start)
    reports = root / "Этапы" / "Reports"
    embed_dir = root / "src" / "preprocessing" / "Create_embeddings"
    if str(embed_dir) not in sys.path:
        sys.path.insert(0, str(embed_dir))
    return {"ROOT": root, "REPORTS": reports, "EMBED_DIR": embed_dir}


if __name__ == "__main__":
    env = bootstrap()
    ROOT = env["ROOT"]
    REPORTS = env["REPORTS"]
    EMBED_DIR = env["EMBED_DIR"]
    print(f"Корень проекта: {ROOT}")
