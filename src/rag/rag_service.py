# -*- coding: utf-8 -*-
"""RAG: поиск в Milvus + генерация ответа через Ollama."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Корень репозитория для import src.*
ROOT = Path(__file__).resolve().parents[2]
EMBED_DIR = ROOT / "src" / "preprocessing" / "Create_embeddings"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(EMBED_DIR) not in sys.path:
    sys.path.insert(0, str(EMBED_DIR))

from model_selector import select_text_model
from multimodal_rag import (
    MultimodalRAG,
    check_vector_db_server,
    get_default_embedding_model,
)
from runtime_config import load_runtime_config
from src.rag.ollama_client import OllamaClient

PUE_SYSTEM = (
    "Ты помощник по Правилам устройства электроустановок (ПУЭ). "
    "Отвечай только на основе приведённого контекста. "
    "Если ответа нет в контексте — так и скажи. "
    "Указывай номера пунктов ПУЭ из контекста."
)

_rag_session: dict[str, Any] = {"key": None, "rag": None}


def close_rag_session() -> None:
    """Закрыть кэш MultimodalRAG (после пакетного eval)."""
    rag = _rag_session.get("rag")
    if rag is not None:
        rag.close()
    _rag_session["key"] = None
    _rag_session["rag"] = None


def _open_rag(
    *,
    host: str,
    port: str,
    collection: str,
    text_model: str,
    text_dim: int | None,
    device_text: str,
    device_clip: str,
    reuse: bool,
) -> MultimodalRAG:
    key = (host, port, collection, text_model, text_dim, device_text, device_clip)
    if reuse and _rag_session["rag"] is not None and _rag_session["key"] == key:
        return _rag_session["rag"]
    close_rag_session()
    rag = MultimodalRAG(
        vector_db_host=host,
        vector_db_port=port,
        collection_name=collection,
        text_model_name=text_model,
        text_dim=text_dim,
        device_text=device_text,
        device_clip=device_clip,
        load_image_model=False,
    )
    rag.load_collection()
    if reuse:
        _rag_session["key"] = key
        _rag_session["rag"] = rag
    return rag


def _format_context(hits: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, h in enumerate(hits, 1):
        score = h.get("score")
        chapter = h.get("chapter", "")
        text = (h.get("text") or "").strip()
        if len(text) > 1200:
            text = text[:1200] + "…"
        parts.append(f"[{i}] (score={score:.3f}, глава {chapter})\n{text}")
    return "\n\n".join(parts)


def answer(
    question: str, *, limit: int | None = None, reuse_rag: bool = False
) -> dict[str, Any]:
    cfg = load_runtime_config()
    vdb = cfg["vector_db"]
    host = vdb["host"]
    port = str(vdb["port"])
    collection = vdb["collection_name"]
    search_limit = limit if limit is not None else int(cfg["query"]["default_limit"])

    if not check_vector_db_server(host, port):
        raise RuntimeError("Milvus недоступен")

    models_cfg = cfg["models"]
    if reuse_rag and _rag_session.get("rag") is not None:
        rag = _rag_session["rag"]
    else:
        meta = MultimodalRAG.get_embedding_meta_from_collection(host, port, collection)
        if meta:
            text_model = meta["text_model"]
            text_dim = meta.get("text_dim")
        else:
            text_model, _ = select_text_model(cfg)
            text_model, text_dim = get_default_embedding_model()
        rag = _open_rag(
            host=host,
            port=port,
            collection=collection,
            text_model=text_model,
            text_dim=text_dim,
            device_text=models_cfg["device_text"],
            device_clip=models_cfg["device_clip"],
            reuse=reuse_rag,
        )
    hits = rag.search_text(question, limit=search_limit)
    if not reuse_rag:
        rag.close()

    context = _format_context(hits)
    prompt = f"Контекст из ПУЭ:\n\n{context}\n\nВопрос: {question}\n\nОтвет:"
    llm = OllamaClient(runtime_cfg=cfg)
    if not llm.health():
        raise RuntimeError("Ollama недоступен")

    text = llm.generate(prompt, system=PUE_SYSTEM)
    return {
        "question": question,
        "answer": text,
        "sources": hits,
        "model": llm.config.model,
    }
