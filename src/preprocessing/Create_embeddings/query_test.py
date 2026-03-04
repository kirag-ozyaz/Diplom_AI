# -*- coding: utf-8 -*-
"""
Тестовый запрос к Multimodal RAG по уже готовой коллекции (без создания коллекции).
Перед запуском должен быть запущен сервер векторной БД и коллекция должна существовать.
"""

import sys

from multimodal_rag import MultimodalRAG, get_default_embedding_model, check_vector_db_server


def main():
    host, port = "localhost", 19530
    collection_name = "diplom_multimodal"
    base_data_path = "data"

    print("🔌 Проверка сервера векторной БД...")
    if not check_vector_db_server(host, port):
        print(f"❌ Сервер векторной БД недоступен: {host}:{port}")
        print("   Запустите сервер (например, через docker-compose) и повторите попытку.")
        sys.exit(1)
    print(f"✅ Сервер векторной БД доступен: {host}:{port}\n")

    # Метаданные эмбеддингов из коллекции — для поиска используем ту же модель и text_dim
    meta = MultimodalRAG.get_embedding_meta_from_collection(host, str(port), collection_name)
    if meta:
        text_model_name = meta["text_model"]
        text_dim = meta["text_dim"]
        print(f"   Модель из метаданных коллекции: {text_model_name}, text_dim={text_dim}\n")
    else:
        text_model_name, text_dim = get_default_embedding_model()
        print(f"   Модель по умолчанию из конфига: {text_model_name}, text_dim={text_dim}\n")

    # Подключение к уже существующей коллекции, без создания и без загрузки CLIP
    rag = MultimodalRAG(
        vector_db_host=host,
        vector_db_port=str(port),
        collection_name=collection_name,
        text_model_name=text_model_name,
        text_dim=text_dim,
        base_data_path=base_data_path,
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
    rag.load_collection()

    print("\n🔍 Тестовый поиск...")
    # results = rag.search_text("система заземления", limit=3)
    results = rag.search_text("# Нулевой защитный и нулевой рабочий проводники", limit=10)

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
            print(f"   🖼️ Изображений: {len(res.get('image_paths') or [])}")

    rag.close()
    print("\n✅ Тест завершён")


if __name__ == "__main__":
    main()
