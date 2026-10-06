# -*- coding: utf-8 -*-
"""RAG: retrieval + LLM (Ollama)."""

from .ollama_client import OllamaClient, OllamaConfig

__all__ = ["OllamaClient", "OllamaConfig", "answer"]


def __getattr__(name: str):
    if name == "answer":
        from .rag_service import answer
        return answer
    raise AttributeError(name)
