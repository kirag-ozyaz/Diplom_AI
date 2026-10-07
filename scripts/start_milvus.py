"""Запуск Milvus standalone: docker compose up -d в infra/milvus.

Диагностика после сбоя: scripts/start_milvus_logs.py (см. infra/milvus/Storage.md).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from notebook_bootstrap import find_project_root

SCRIPTS_DIR = Path(__file__).resolve().parent


def start_milvus(*, root: Path | None = None, skip_compute_bootstrap: bool = False) -> int:
    project_root = find_project_root(root)

    if not skip_compute_bootstrap:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from compute_detect import ensure_runtime_config  # noqa: E402

        ensure_runtime_config(apply=True, print_report=True)
        print()

    milvus_dir = project_root / "infra" / "milvus"
    compose_file = milvus_dir / "docker-compose.yml"
    if not compose_file.is_file():
        print(f"Не найден файл: {compose_file}", file=sys.stderr)
        return 1

    print(f"Каталог compose: {milvus_dir}")
    up = subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=milvus_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if up.returncode != 0:
        print(
            "Ошибка docker compose. Проверьте, что Docker Desktop запущен.",
            file=sys.stderr,
        )
        return up.returncode

    subprocess.run(
        ["docker", "compose", "ps"],
        cwd=milvus_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(start_milvus())
