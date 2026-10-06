"""Запуск Docker для отчёта этапа 4: Milvus (3 контейнера) + Ollama."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from notebook_bootstrap import find_project_root


def start_report_docker(
    *,
    root: Path | None = None,
    pull_ollama: bool = False,
    skip_ollama: bool = False,
) -> int:
    project_root = find_project_root(root)
    scripts = project_root / "scripts"

    print("=== Milvus (etcd, minio, standalone) ===")
    milvus = subprocess.run(
        [sys.executable, str(scripts / "start_milvus.py")],
        cwd=project_root,
    )
    if milvus.returncode != 0:
        return milvus.returncode

    if skip_ollama:
        print("Ollama пропущен (--skip-ollama).")
        return 0

    print("\n=== Ollama ===")
    ollama_cmd = [sys.executable, str(scripts / "start_ollama.py")]
    if pull_ollama:
        ollama_cmd.append("--pull")
    ollama = subprocess.run(ollama_cmd, cwd=project_root)
    return ollama.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Milvus + Ollama через docker compose (отчёт этапа 4)."
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="После старта Ollama: ollama pull модели из конфига",
    )
    parser.add_argument(
        "--skip-ollama",
        action="store_true",
        help="Только Milvus (достаточно для Hit@k и demo search)",
    )
    args = parser.parse_args()
    raise SystemExit(
        start_report_docker(pull_ollama=args.pull, skip_ollama=args.skip_ollama)
    )


if __name__ == "__main__":
    main()
