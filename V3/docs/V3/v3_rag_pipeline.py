"""
Модуль генерации ответов RAG V3 (Qwen2.5:14b-instruct via Ollama).
"""

import json
from typing import Any, Dict, List

import requests

PUE_SYSTEM_PROMPT = (
    "Ты эксперт-помощник по Правилам устройства электроустановок (ПУЭ). "
    "Отвечай строго на основе предоставленного контекста. "
    "Если ответа нет в контексте — явно сообщи об этом. "
    "Обязательно указывай точные номера пунктов ПУЭ из контекста."
)

class V3RAGPipeline:
    def __init__(self, ollama_url: str = "http://localhost:11434", model_name: str = "qwen2.5:14b-instruct-q4_K_M"):
        self.ollama_url = ollama_url
        self.model_name = model_name

    def generate_answer(self, query: str, retrieved_chunks: List[Dict[str, Any]], top_k: int = 5) -> Dict[str, Any]:
        context_blocks = []
        for i, chunk in enumerate(retrieved_chunks[:top_k], 1):
            clause = chunk.get("metadata", {}).get("Clause", "ПУЭ")
            content = chunk.get("content", "").strip()
            context_blocks.append(f"[{i}] Фрагмент (Пункт {clause}):\n{content}")
        
        context_text = "\n\n".join(context_blocks)
        prompt = f"Контекст из ПУЭ:\n{context_text}\n\nВопрос пользователя: {query}\nОтвет:"

        payload = {
            "model": self.model_name,
            "system": PUE_SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 512,
                "num_ctx": 8192
            }
        }

        try:
            resp = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            return {
                "answer": result.get("response", "").strip(),
                "sources": [c.get("metadata", {}).get("Clause") for c in retrieved_chunks[:top_k]],
                "status": "success"
            }
        except Exception as exc:
            return {"answer": f"Ошибка генерации: {exc}", "sources": [], "status": "error"}