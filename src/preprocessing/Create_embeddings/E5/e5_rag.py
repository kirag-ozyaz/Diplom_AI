# -*- coding: utf-8 -*-
"""Подключение к коллекции diplom_multimodal_e5 с префиксом query: при поиске."""

from __future__ import annotations

import sys
from pathlib import Path

_E5_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_E5_DIR.parent))
sys.path.insert(0, str(_E5_DIR))

from multimodal_rag import MultimodalRAG, check_vector_db_server
from runtime_config import load_runtime_config, resolve_repo_path

BASELINE_COLLECTION = "diplom_multimodal"


def open_text_rag() -> tuple[MultimodalRAG, dict]:
    """Открывает коллекцию из rag_runtime_e5.json. Базовую коллекцию не трогает."""
    cfg = load_runtime_config()
    vdb = cfg["vector_db"]
    host = vdb["host"]
    port = str(vdb["port"])
    collection = vdb["collection_name"]
    if collection == BASELINE_COLLECTION:
        raise SystemExit(
            f"Отказ: конфиг E5 указывает на {BASELINE_COLLECTION}. "
            "Поиск с query: для этой коллекции не запускается."
        )
    if not check_vector_db_server(host, port):
        raise SystemExit(
            f"Milvus недоступен: {host}:{port}. "
            "Запустите scripts/infra_start_system/start_milvus.py."
        )

    meta = MultimodalRAG.get_embedding_meta_from_collection(host, port, collection)
    models = cfg["models"]
    if meta:
        text_model = meta["text_model"]
        text_dim = meta.get("text_dim")
    else:
        text_model = models["text_model_name"]
        text_dim = None

    print(f"E5: коллекция «{collection}», модель {text_model}.", flush=True)
    rag = MultimodalRAG(
        vector_db_host=host,
        vector_db_port=port,
        collection_name=collection,
        text_model_name=text_model,
        text_dim=text_dim,
        device_text=models["device_text"],
        device_clip=models["device_clip"],
        base_data_path=str(resolve_repo_path(cfg["paths"]["base_data_path"])),
        load_image_model=False,
        e5_query_prefix=True,
    )
    rag.load_collection()
    print("Коллекция Milvus открыта, модель embedding готова.", flush=True)
    desc = ""
    if rag.collection is not None:
        desc = (rag.collection.describe() or {}).get("description") or ""
    if "e5_passage=1" not in desc:
        print(
            " Внимание: в описании коллекции нет e5_passage=1. "
            "Векторы могли быть залиты без passage:."
        )
    return rag, cfg
