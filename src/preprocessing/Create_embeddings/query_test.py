# -*- coding: utf-8 -*-
"""
Тестовый запрос к Multimodal RAG по уже готовой коллекции (без создания коллекции).
Перед запуском должен быть запущен сервер векторной БД и коллекция должна существовать.
"""

import sys

print("▶ query_test: старт", flush=True)
print(
    "⏳ Загрузка ML-библиотек (torch, sentence-transformers) — "
    "при первом запуске может занять 1–3 мин без вывода, это нормально",
    flush=True,
)

from multimodal_rag import MultimodalRAG, get_default_embedding_model, check_vector_db_server
from runtime_config import load_runtime_config, resolve_repo_path
from model_selector import select_text_model

print(" Библиотеки загружены", flush=True)


def main():
    cfg = load_runtime_config()
    vector_db = cfg["vector_db"]
    paths = cfg["paths"]
    models = cfg["models"]
    query_test_cfg = cfg["query_test"]

    host = vector_db["host"]
    port = str(vector_db["port"])
    collection_name = vector_db["collection_name"]
    base_data_path = str(resolve_repo_path(paths["base_data_path"]))

    print(" Проверка сервера векторной БД...", flush=True)
    if not check_vector_db_server(host, port):
        print(f" Сервер векторной БД недоступен: {host}:{port}", flush=True)
        print("   Запустите сервер (например, через docker-compose) и повторите попытку.", flush=True)
        sys.exit(1)
    print(f" Сервер векторной БД доступен: {host}:{port}\n", flush=True)

    print(" Чтение метаданных коллекции...", flush=True)
    # Метаданные эмбеддингов из коллекции — для поиска используем ту же модель и text_dim
    meta = MultimodalRAG.get_embedding_meta_from_collection(host, str(port), collection_name)
    if meta:
        text_model_name = meta["text_model"]
        text_dim = meta["text_dim"]
        print(f"   Модель из метаданных коллекции: {text_model_name}, text_dim={text_dim}\n", flush=True)
    else:
        auto_model, reason = select_text_model(cfg)
        text_model_name = auto_model
        text_dim = None
        if not text_model_name:
            text_model_name, text_dim = get_default_embedding_model()
            print(f"   Модель по умолчанию из embedding_config: {text_model_name}, text_dim={text_dim}\n")
        else:
            print(f"   Автовыбор модели: {text_model_name} ({reason})\n")

    # Подключение к уже существующей коллекции, без создания и без загрузки CLIP
    print(f" Загрузка embedding-модели ({text_model_name})...", flush=True)
    rag = MultimodalRAG(
        vector_db_host=host,
        vector_db_port=str(port),
        collection_name=collection_name,
        text_model_name=text_model_name,
        text_dim=text_dim,
        base_data_path=base_data_path,
        device_text=models["device_text"],
        device_clip=models["device_clip"],
        load_image_model=False,
    )
    # Старый вариант без учёта метаданных коллекции:
    # rag = MultimodalRAG(
    #     vector_db_host=host,
    #     vector_db_port=str(port),
    #     collection_name=collection_name,
    #     base_data_path=base_data_path,
    #     load_image_model=False,
    # )

    # Загрузка готовой коллекции в память для поиска (не создаём новую)
    print(" Загрузка коллекции Milvus в память...", flush=True)
    rag.load_collection()

    search_text = str(query_test_cfg["search_text"])
    test_limit = int(query_test_cfg["limit"])
    print(f"\n Тестовый поиск...")
    print(f" Текст для поиска: {search_text}")
    # results = rag.search_text("система заземления", limit=3)

    results = rag.search_text(search_text, limit=test_limit)

    for i, res in enumerate(results, 1):
        print(f"\n{i}. Score: {res['score']:.4f}")
        print(f"   Глава: {res['chapter']}")
        text = res.get("text") or ""
        if text.strip():
            # snippet = text[:150] + "..." if len(text) > 150 else text
            snippet = text
            print(f"   Текст: {snippet}")
        else:
            print(f"   Текст: (пусто)")
        if res.get("has_image"):
            print(f"    Изображений: {len(res.get('image_paths') or [])}")

    rag.close()
    print("\n Тест завершён")


if __name__ == "__main__":
    main()
