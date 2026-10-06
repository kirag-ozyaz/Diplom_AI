# -*- coding: utf-8 -*-
"""Тест полного RAG: Milvus + Ollama. Запуск: python scripts/test_rag_ollama.py [вопрос]"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.rag_service import answer


def main() -> None:
    q = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Что такое нулевой защитный проводник по ПУЭ?"
    )
    print(f"Вопрос: {q}\n")
    try:
        result = answer(q)
    except RuntimeError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    print(f"Модель LLM: {result['model']}")
    print(f"Найдено фрагментов: {len(result['sources'])}")
    if result["sources"]:
        top = result["sources"][0]
        print(f"Top-1 score: {top.get('score')}, chapter: {top.get('chapter')}")
    print("\n--- Ответ ---\n")
    print(result["answer"])


if __name__ == "__main__":
    main()
