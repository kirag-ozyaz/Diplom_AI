#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тестовый скрипт: выводит рекомендованную embedding-модель."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EMBEDDINGS_DIR = ROOT / "src" / "preprocessing" / "Create_embeddings"
sys.path.insert(0, str(EMBEDDINGS_DIR))

from model_selector import detect_gpu_info, select_ollama_model, select_text_model  # noqa: E402
from runtime_config import DEFAULT_CONFIG_PATH, load_runtime_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Показать рекомендованную модель эмбеддингов по текущему конфигу и GPU."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Путь к runtime-конфигу (по умолчанию: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести результат в формате JSON.",
    )
    args = parser.parse_args()

    runtime_cfg = load_runtime_config(args.config)
    model_name, reason = select_text_model(runtime_cfg)
    ollama_model, ollama_reason = select_ollama_model(runtime_cfg)
    gpu_info = detect_gpu_info()

    payload = {
        "config_path": str(args.config),
        "recommended_text_model": model_name,
        "reason": reason,
        "recommended_ollama_model": ollama_model,
        "ollama_reason": ollama_reason,
        "gpu": {
            "detected": gpu_info is not None,
            "name": gpu_info.name if gpu_info else None,
            "vram_gb": gpu_info.vram_gb if gpu_info else None,
            "source": gpu_info.source if gpu_info else None,
        },
        "auto_select_enabled": bool(
            runtime_cfg.get("model_selection", {}).get("auto_select_text_model", False)
        ),
        "auto_select_ollama_enabled": bool(
            runtime_cfg.get("model_selection", {}).get("auto_select_ollama_model", False)
        ),
        "fallback_text_model": runtime_cfg.get("models", {}).get("text_model_name"),
        "fallback_ollama_model": (runtime_cfg.get("ollama") or {}).get("model"),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"config: {payload['config_path']}")
    print(f"auto_select_text_model: {payload['auto_select_enabled']}")
    if payload["gpu"]["detected"]:
        print(
            f"gpu: {payload['gpu']['name']} ({payload['gpu']['vram_gb']} GB, {payload['gpu']['source']})"
        )
    else:
        print("gpu: not detected")
    print(f"recommended_text_model: {payload['recommended_text_model']}")
    print(f"reason: {payload['reason']}")
    print(f"fallback_text_model: {payload['fallback_text_model']}")
    print(f"auto_select_ollama_model: {payload['auto_select_ollama_enabled']}")
    print(f"recommended_ollama_model: {payload['recommended_ollama_model']}")
    print(f"ollama_reason: {payload['ollama_reason']}")
    print(f"fallback_ollama_model: {payload['fallback_ollama_model']}")


if __name__ == "__main__":
    main()
