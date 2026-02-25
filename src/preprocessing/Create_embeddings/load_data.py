# -*- coding: utf-8 -*-
"""
Скрипт загрузки данных в Multimodal RAG систему
"""

from multimodal_rag import MultimodalRAG

def main():
    print("🚀 Запуск загрузки данных в Multimodal RAG...")
    
    # Инициализация системы
    rag = MultimodalRAG(
        milvus_host="localhost",
        milvus_port="19530",
        collection_name="diplom_multimodal",
        text_model_name="BAAI/bge-small-en-v1.5",
        clip_model_name="ViT-B-32",
        device_text="cuda",      # Текст на GPU
        device_clip="cpu",       # CLIP на CPU (экономия VRAM!)
        base_data_path="data"
    )
    
    # Создание коллекции
    rag.create_collection(drop_existing=True)
    
    # Загрузка данных
    rag.load_from_jsonl_folder(
        jsonl_folder="data/chunked",
        batch_size=32,
        skip_existing=False
    )
    
    # Загрузка в память для поиска
    rag.load_collection()
    
    # Статистика
    stats = rag.get_collection_stats()
    print(f"\n📊 Статистика коллекции:")
    print(f"   Название: {stats['name']}")
    print(f"   Сущностей: {stats['num_entities']}")
    print(f"   Поля: {stats['schema']}")
    
    # Тестовый поиск
    print("\n🔍 Тестовый поиск...")
    results = rag.search_text("система заземления TN-C", limit=3)
    
    for i, res in enumerate(results, 1):
        print(f"\n{i}. Score: {res['score']:.4f}")
        print(f"   Глава: {res['chapter']}")
        print(f"   Текст: {res['text'][:150]}...")
        if res['has_image']:
            print(f"   🖼️ Изображений: {len(res['image_paths'])}")
    
    rag.close()
    print("\n✅ Загрузка завершена успешно!")

if __name__ == "__main__":
    main()