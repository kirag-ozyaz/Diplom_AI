# -*- coding: utf-8 -*-
"""Клиент Ollama API для генерации ответов RAG."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from src.preprocessing.Create_embeddings.runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    load_runtime_config,
)


@dataclass
class OllamaConfig:
    host: str
    model: str
    timeout_sec: float
    temperature: float
    num_predict: int

    @classmethod
    def from_runtime(cls, cfg: dict[str, Any] | None = None) -> "OllamaConfig":
        full = cfg if cfg is not None else load_runtime_config()
        block = full.get("ollama") or {}
        base = DEFAULT_RUNTIME_CONFIG["ollama"]
        env_host = os.getenv("OLLAMA_HOST")
        model = block.get("model") or base["model"]
        if full.get("model_selection", {}).get("auto_select_ollama_model", False):
            import sys
            from pathlib import Path

            embed_dir = Path(__file__).resolve().parents[1] / "preprocessing" / "Create_embeddings"
            if str(embed_dir) not in sys.path:
                sys.path.insert(0, str(embed_dir))
            from model_selector import select_ollama_model  # noqa: E402

            model, _ = select_ollama_model(full, ollama_compose_mode="gpu")
        return cls(
            host=(env_host or block.get("host") or base["host"]).rstrip("/"),
            model=model,
            timeout_sec=float(block.get("timeout_sec", base["timeout_sec"])),
            temperature=float(block.get("temperature", base["temperature"])),
            num_predict=int(block.get("num_predict", base["num_predict"])),
        )


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None, runtime_cfg: dict | None = None) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = OllamaConfig.from_runtime(runtime_cfg)

    @property
    def base_url(self) -> str:
        return self.config.host.rstrip("/")

    def health(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        r = httpx.get(f"{self.base_url}/api/tags", timeout=30.0)
        r.raise_for_status()
        data = r.json()
        models = data.get("models") or []
        names: list[str] = []
        for m in models:
            name = m.get("name") if isinstance(m, dict) else None
            if name:
                names.append(name)
        return names

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        stream: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.config.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.num_predict,
            },
        }
        if system:
            payload["system"] = system

        r = httpx.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.config.timeout_sec,
        )
        r.raise_for_status()
        body = r.json()
        return (body.get("response") or "").strip()
