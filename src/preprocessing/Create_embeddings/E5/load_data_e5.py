# -*- coding: utf-8 -*-
"""
Заливка тех же JSONL в отдельную коллекцию Milvus с префиксом E5 «passage: ».

Конфиг: E5/runtime_config.py → E5/rag_runtime_e5.json (коллекция diplom_multimodal_e5).
config/rag_runtime.json и коллекция diplom_multimodal не используются.
JSONL в data/chunked только читаются.
"""

import asyncio
import sys
from pathlib import Path

_E5_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_E5_DIR.parent))
sys.path.insert(0, str(_E5_DIR))

from multimodal_rag import MultimodalRAG
from runtime_config import E5_CONFIG_PATH, load_runtime_config, resolve_repo_path

# Базовая коллекция опыта 0. Этот скрипт её не открывает и не удаляет.
BASELINE_COLLECTION = "diplom_multimodal"
E5_TEXT_MODEL = "intfloat/multilingual-e5-base"


def main():
    print(" Запуск загрузки E5 (passage:) в отдельную коллекцию...")
    if not E5_CONFIG_PATH.is_file():
        raise SystemExit(f"Нет конфига: {E5_CONFIG_PATH}")

    cfg = load_runtime_config()
    vector_db = cfg["vector_db"]
    paths = cfg["paths"]
    models = cfg["models"]
    load_cfg = cfg["load_data"]
    e5_collection = vector_db["collection_name"]

    if e5_collection == BASELINE_COLLECTION:
        raise SystemExit(
            f"Отказ: в {E5_CONFIG_PATH.name} collection_name={e5_collection}. "
            "База diplom_multimodal не должна перезаписываться."
        )

    text_model_name = models.get("text_model_name") or ""
    if text_model_name != E5_TEXT_MODEL:
        raise SystemExit(
            f"Отказ: в {E5_CONFIG_PATH.name} text_model_name={text_model_name!r}, "
            f"для этой коллекции нужна {E5_TEXT_MODEL}."
        )

    chunked_root = resolve_repo_path(paths["chunked_path"])
    print(f"   Конфиг: {E5_CONFIG_PATH}")
    print(f"   Текстовая модель: {text_model_name}")
    print(f"   JSONL (только чтение): {chunked_root}")
    print(f"   Базовая коллекция не изменяется: {BASELINE_COLLECTION}")
    print(
        f"   Векторная БД: {vector_db['host']}:{vector_db['port']} "
        f"(collection={e5_collection}, prefix=passage:)"
    )

    rag = MultimodalRAG(
        vector_db_host=vector_db["host"],
        vector_db_port=str(vector_db["port"]),
        collection_name=e5_collection,
        text_model_name=text_model_name,
        clip_model_name=models["clip_model_name"],
        device_text=models["device_text"],
        device_clip=models["device_clip"],
        base_data_path=str(chunked_root),
        e5_passage_prefix=True,
    )

    # drop_existing снимает только diplom_multimodal_e5 (имя задано выше).
    rag.create_collection(drop_existing=True)

    use_async = bool(load_cfg["use_async"])
    jsonl_folder = chunked_root
    load_kwargs = dict(
        jsonl_folder=str(jsonl_folder),
        batch_size=int(load_cfg["batch_size"]),
        skip_existing=bool(load_cfg["skip_existing"]),
        log_every_batches=int(load_cfg["log_every_batches"]),
        log_file_summary=bool(load_cfg["log_file_summary"]),
    )
    if use_async:
        asyncio.run(rag.load_from_jsonl_folder_async(**load_kwargs))
    else:
        rag.load_from_jsonl_folder(**load_kwargs)

    rag.load_collection()

    stats = rag.get_collection_stats()
    print("\n Статистика коллекции:")
    print(f"   Название: {stats['name']}")
    print(f"   Сущностей: {stats['num_entities']}")
    print(f"   Поля: {stats['schema']}")
    meta = rag.get_collection_embedding_meta()
    if meta:
        print(f"   Метаданные эмбеддингов: text_model={meta['text_model']}, text_dim={meta['text_dim']}")
    print("   Префикс векторов: passage:")

    rag.close()
    print("\n Загрузка E5 завершена. Коллекция diplom_multimodal не изменялась.")


if __name__ == "__main__":
    main()
