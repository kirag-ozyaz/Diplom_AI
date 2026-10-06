# -*- coding: utf-8 -*-
"""
Запуск Ollama в Docker с выбором GPU или CPU compose.
Из корня: python scripts/start_ollama.py [--pull] [--check-only]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLLAMA_DIR = ROOT / "infra" / "docker" / "Dockerfile.ollama"

sys.path.insert(0, str(ROOT / "scripts"))
from compute_detect import (  # noqa: E402
    apply_ollama_model_to_config,
    build_compute_report,
)


def _ollama_model_for_run(report) -> str:
    sys.path.insert(0, str(ROOT / "src" / "preprocessing" / "Create_embeddings"))
    from runtime_config import load_runtime_config as load_cfg  # noqa: E402
    from model_selector import select_ollama_model  # noqa: E402

    cfg = load_cfg()
    model, _ = select_ollama_model(cfg, ollama_compose_mode=report.ollama_compose_mode)
    return model


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Старт Ollama (GPU или CPU compose).")
    parser.add_argument("--check-only", action="store_true", help="Только проверка, без docker compose")
    parser.add_argument("--pull", action="store_true", help="После старта: ollama pull модели из конфига")
    parser.add_argument(
        "--apply-config",
        action="store_true",
        help="Записать рекомендуемую ollama.model в config/rag_runtime.json (если auto_select_ollama_model)",
    )
    args = parser.parse_args()

    report = build_compute_report()
    print(f"Режим Ollama: {report.ollama_compose_mode.upper()}")
    print(f"LLM (рекомендация): {report.ollama_model_recommended} — {report.ollama_model_reason}")
    for note in report.notes:
        print(f"  {note}")

    cfg_path = ROOT / "config" / "rag_runtime.json"
    if args.apply_config:
        if apply_ollama_model_to_config(cfg_path, report.ollama_model_recommended):
            print(f"Обновлён {cfg_path}: ollama.model={report.ollama_model_recommended}")
        else:
            print("ollama.model не изменён (auto_select_ollama_model=false)")

    if args.check_only:
        return

    if not report.docker_available:
        print("Docker не найден или недоступен.")
        sys.exit(1)

    files = ["-f", "docker-compose.yml"]
    if report.ollama_compose_mode == "gpu":
        files.extend(["-f", "docker-compose.gpu.yml"])

    cmd = ["docker", "compose", *files, "up", "-d"]
    print(f"Команда: cd {OLLAMA_DIR} && {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=OLLAMA_DIR)
    if proc.returncode != 0:
        sys.exit(proc.returncode)

    print("Контейнер ollama запущен на http://localhost:11434")

    if args.pull:
        model = _ollama_model_for_run(report)
        print(f"Скачивание модели {model}...")
        pull = subprocess.run(["docker", "exec", "ollama", "ollama", "pull", model])
        sys.exit(pull.returncode)


if __name__ == "__main__":
    main()
