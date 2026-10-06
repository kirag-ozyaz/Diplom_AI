# -*- coding: utf-8 -*-
"""
Проверка Ollama: API, модель из config/rag_runtime.json, пробный ответ.
Запуск из корня: python scripts/test_ollama.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.preprocessing.Create_embeddings.runtime_config import load_runtime_config
from src.rag.ollama_client import OllamaClient


def main() -> None:
    cfg = load_runtime_config()
    ollama_cfg = cfg.get("ollama") or {}
    client = OllamaClient(runtime_cfg=cfg)

    print(f"Ollama host: {client.config.host}")
    print(f"Model (config): {client.config.model}")

    if not client.health():
        print("FAIL: Ollama API недоступен. Запустите infra/docker/Dockerfile.ollama")
        sys.exit(1)
    print("OK: API /api/tags")

    models = client.list_models()
    print(f"Models in container: {models or '(пусто)'}")

    model = client.config.model
    if model not in models and not any(m.startswith(model.split(":")[0]) for m in models):
        print(f"WARN: модель {model!r} не найдена. Выполните:")
        print(f"  docker exec ollama ollama pull {model}")

    prompt = "Кратко одним предложением: что такое ПУЭ?"
    system = "Отвечай по-русски, кратко, без выдумок."
    print(f"\nPrompt: {prompt}")
    print("Generating...")
    text = client.generate(prompt, system=system)
    print("\n--- Ответ ---")
    print(text)
    print("---")


if __name__ == "__main__":
    main()
