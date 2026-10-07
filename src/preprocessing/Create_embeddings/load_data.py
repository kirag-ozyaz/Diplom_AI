# -*- coding: utf-8 -*-
"""
Скрипт загрузки данных в Multimodal RAG систему
"""

from multimodal_rag import MultimodalRAG, get_default_embedding_model
import asyncio
from runtime_config import load_runtime_config, resolve_repo_path
from model_selector import select_text_model

def main():
    print(" Запуск загрузки данных в Multimodal RAG...")
    cfg = load_runtime_config()
    vector_db = cfg["vector_db"]
    paths = cfg["paths"]
    models = cfg["models"]
    load_cfg = cfg["load_data"]

    chunked_root = resolve_repo_path(paths["chunked_path"])

    text_model_name, selection_reason = select_text_model(cfg)
    if not text_model_name:
        text_model_name, _ = get_default_embedding_model()
        selection_reason = "fallback to embedding_config default model"
    print(f"   Текстовая модель: {text_model_name}")
    print(f"   Выбор модели: {selection_reason}")
    print(
        f"   Векторная БД: {vector_db['host']}:{vector_db['port']} "
        f"(collection={vector_db['collection_name']})"
    )

    # Инициализация: text_dim подставляется из embedding_config.json по text_model_name
    rag = MultimodalRAG(
        vector_db_host=vector_db["host"],
        vector_db_port=str(vector_db["port"]),
        collection_name=vector_db["collection_name"],
        text_model_name=text_model_name,
        clip_model_name=models["clip_model_name"],
        device_text=models["device_text"],
        device_clip=models["device_clip"],
        base_data_path=str(chunked_root),
    )
    # Чтобы принудительно использовать другую модель — передайте явно, например:
    # rag = MultimodalRAG(..., text_model_name="intfloat/multilingual-e5-base", ...)

    # Создание коллекции
    rag.create_collection(drop_existing=bool(load_cfg["drop_existing"]))
    
    # Загрузка данных
    # Можно грузить синхронно (по умолчанию) или асинхронно.
    # Асинхронный режим полезен, если вы хотите, чтобы event loop оставался отзывчивым
    # (например, параллельно крутится UI/бот), т.к. insert/flush вынесены в thread.
    use_async = bool(load_cfg["use_async"])
    jsonl_folder = chunked_root

    if use_async:
        asyncio.run(
            rag.load_from_jsonl_folder_async(
                jsonl_folder=str(jsonl_folder),
                batch_size=int(load_cfg["batch_size"]),
                skip_existing=bool(load_cfg["skip_existing"]),
                log_every_batches=int(load_cfg["log_every_batches"]),
                log_file_summary=bool(load_cfg["log_file_summary"]),
            )
        )
    else:
        rag.load_from_jsonl_folder(
            jsonl_folder=str(jsonl_folder),
            batch_size=int(load_cfg["batch_size"]),
            skip_existing=bool(load_cfg["skip_existing"]),
            log_every_batches=int(load_cfg["log_every_batches"]),
            log_file_summary=bool(load_cfg["log_file_summary"]),
        )
    
    # Загрузка в память для поиска
    rag.load_collection()
    
    # Статистика и метаданные эмбеддингов (для поиска использовать те же text_model_name и text_dim)
    stats = rag.get_collection_stats()
    print(f"\n Статистика коллекции:")
    print(f"   Название: {stats['name']}")
    print(f"   Сущностей: {stats['num_entities']}")
    print(f"   Поля: {stats['schema']}")
    meta = rag.get_collection_embedding_meta()
    if meta:
        print(f"   Метаданные эмбеддингов: text_model={meta['text_model']}, text_dim={meta['text_dim']}")
    
    # Тестовый поиск
    # print("\n Тестовый поиск...")
    # results = rag.search_text("система заземления", limit=3)
    #
    # for i, res in enumerate(results, 1):
    #     print(f"\n{i}. Score: {res['score']:.4f}")
    #     print(f"   Глава: {res['chapter']}")
    #     text = res.get('text') or ''
    #     if text.strip():
    #         snippet = text[:150] + "..." if len(text) > 150 else text
    #         print(f"   Текст: {snippet}")
    #     else:
    #         print(f"   Текст: (пусто)")
    #     if res.get('has_image'):
    #         print(f"    Изображений: {len(res.get('image_paths') or [])}")
    
    rag.close()
    print("\n Загрузка завершена успешно!")

if __name__ == "__main__":
    main()