# -*- coding: utf-8 -*-
"""
Скрипт загрузки данных в Multimodal RAG систему
"""

from multimodal_rag import MultimodalRAG, get_default_embedding_model
import asyncio
from pathlib import Path

def main():

    print("🚀 Запуск загрузки данных в Multimodal RAG...")
    ROOT = Path(__file__).resolve().parent.parent.parent.parent
    chunked_root = ROOT / "data" / "chunked"

    # Модель для загрузки берётся из embedding_config.json (default_text_model)
    # text_model_name, _ = get_default_embedding_model()
    # print(f"   Модель из конфига (default_text_model): {text_model_name}")
    text_model_name = "intfloat/multilingual-e5-base"
    print(f"   Модель из конфига: {text_model_name}")

    # Инициализация: text_dim подставляется из embedding_config.json по text_model_name
    rag = MultimodalRAG(
        vector_db_host="localhost",
        vector_db_port="19530",
        collection_name="diplom_multimodal",
        text_model_name=text_model_name,
        clip_model_name="ViT-B-32",
        device_text="cuda",
        device_clip="cpu",
        base_data_path=str(chunked_root)
    )
    # Чтобы принудительно использовать другую модель — передайте явно, например:
    # rag = MultimodalRAG(..., text_model_name="intfloat/multilingual-e5-base", ...)

    # Создание коллекции
    rag.create_collection(drop_existing=True)
    
    # Загрузка данных
    # Можно грузить синхронно (по умолчанию) или асинхронно.
    # Асинхронный режим полезен, если вы хотите, чтобы event loop оставался отзывчивым
    # (например, параллельно крутится UI/бот), т.к. insert/flush вынесены в thread.
    use_async = True
    jsonl_folder = chunked_root

    if use_async:
        asyncio.run(
            rag.load_from_jsonl_folder_async(
                jsonl_folder=str(jsonl_folder),
                batch_size=32,
                skip_existing=False,
                log_every_batches=1,
                log_file_summary=True
            )
        )
    else:
        rag.load_from_jsonl_folder(
            jsonl_folder=str(jsonl_folder),
            batch_size=32,
            skip_existing=False,
            log_every_batches=1,
            log_file_summary=True
        )
    
    # Загрузка в память для поиска
    rag.load_collection()
    
    # Статистика и метаданные эмбеддингов (для поиска использовать те же text_model_name и text_dim)
    stats = rag.get_collection_stats()
    print(f"\n📊 Статистика коллекции:")
    print(f"   Название: {stats['name']}")
    print(f"   Сущностей: {stats['num_entities']}")
    print(f"   Поля: {stats['schema']}")
    meta = rag.get_collection_embedding_meta()
    if meta:
        print(f"   Метаданные эмбеддингов: text_model={meta['text_model']}, text_dim={meta['text_dim']}")
    
    # Тестовый поиск
    # print("\n🔍 Тестовый поиск...")
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
    #         print(f"   🖼️ Изображений: {len(res.get('image_paths') or [])}")
    
    rag.close()
    print("\n✅ Загрузка завершена успешно!")

if __name__ == "__main__":
    main()