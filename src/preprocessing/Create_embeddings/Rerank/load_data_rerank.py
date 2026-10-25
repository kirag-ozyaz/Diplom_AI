# -*- coding: utf-8 -*-
"""
Заливка тех же JSONL в отдельную коллекцию Milvus опыта 2.

Векторы как у опыта 1: префикс E5 «passage: », модель multilingual-e5-base.
Коллекция: diplom_multimodal_e5_rerank.
Коллекции diplom_multimodal и diplom_multimodal_e5 этот скрипт не открывает и не удаляет.
JSONL в data/chunked только читаются.
"""

import asyncio
import sys
from pathlib import Path

_RERANK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_RERANK_DIR.parent))
sys.path.insert(0, str(_RERANK_DIR))

from multimodal_rag import MultimodalRAG
from runtime_config import (
    PROTECTED_COLLECTIONS,
    RERANK_COLLECTION,
    RERANK_CONFIG_PATH,
    load_runtime_config,
    resolve_repo_path,
)

E5_TEXT_MODEL = "intfloat/multilingual-e5-base"


def main():
    print(" Запуск загрузки опыта 2 (passage:, коллекция реранка)...")
    if not RERANK_CONFIG_PATH.is_file():
        raise SystemExit(f"Нет конфига: {RERANK_CONFIG_PATH}")

    cfg = load_runtime_config()
    vector_db = cfg["vector_db"]
    paths = cfg["paths"]
    models = cfg["models"]
    load_cfg = cfg["load_data"]
    collection_name = vector_db["collection_name"]

    if collection_name in PROTECTED_COLLECTIONS:
        raise SystemExit(
            f"Отказ: в {RERANK_CONFIG_PATH.name} collection_name={collection_name}. "
            "Коллекции опытов 0 и 1 не должны перезаписываться."
        )
    if collection_name != RERANK_COLLECTION:
        raise SystemExit(
            f"Отказ: ожидается коллекция {RERANK_COLLECTION}, в конфиге {collection_name}."
        )

    text_model_name = models.get("text_model_name") or ""
    if text_model_name != E5_TEXT_MODEL:
        raise SystemExit(
            f"Отказ: в {RERANK_CONFIG_PATH.name} text_model_name={text_model_name!r}, "
            f"для этой коллекции нужна {E5_TEXT_MODEL}."
        )

    chunked_root = resolve_repo_path(paths["chunked_path"])
    print(f"   Конфиг: {RERANK_CONFIG_PATH}")
    print(f"   Текстовая модель: {text_model_name}")
    print(f"   JSONL (только чтение): {chunked_root}")
    print(f"   Не изменяются: {', '.join(sorted(PROTECTED_COLLECTIONS))}")
    print(
        f"   Векторная БД: {vector_db['host']}:{vector_db['port']} "
        f"(collection={collection_name}, prefix=passage:)"
    )

    rag = MultimodalRAG(
        vector_db_host=vector_db["host"],
        vector_db_port=str(vector_db["port"]),
        collection_name=collection_name,
        text_model_name=text_model_name,
        clip_model_name=models["clip_model_name"],
        device_text=models["device_text"],
        device_clip=models["device_clip"],
        base_data_path=str(chunked_root),
        e5_passage_prefix=True,
    )

    # drop_existing снимает только diplom_multimodal_e5_rerank.
    rag.create_collection(drop_existing=True)

    use_async = bool(load_cfg["use_async"])
    load_kwargs = dict(
        jsonl_folder=str(chunked_root),
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
        print(
            f"   Метаданные эмбеддингов: text_model={meta['text_model']}, "
            f"text_dim={meta['text_dim']}"
        )
    print("   Префикс векторов: passage:")

    rag.close()
    print(
        "\n Загрузка опыта 2 завершена. "
        "Коллекции diplom_multimodal и diplom_multimodal_e5 не изменялись."
    )


if __name__ == "__main__":
    main()
