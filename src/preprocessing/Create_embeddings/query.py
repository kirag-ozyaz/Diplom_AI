# -*- coding: utf-8 -*-
"""
Скрипт поиска в Multimodal RAG системе
"""

from multimodal_rag import MultimodalRAG, get_default_embedding_model, check_vector_db_server
import os
import sys


def main():
    print("🔍 Поиск в Multimodal RAG системе...")

    vector_db_host = "localhost"
    vector_db_port = "19530"
    collection_name = "diplom_multimodal"
    base_data_path = "data"

    print("🔌 Проверка сервера векторной БД...")
    if not check_vector_db_server(vector_db_host, vector_db_port):
        print(f"❌ Сервер векторной БД недоступен: {vector_db_host}:{vector_db_port}")
        print("   Запустите сервер (например, через docker-compose) и повторите попытку.")
        sys.exit(1)
    print(f"✅ Сервер векторной БД доступен: {vector_db_host}:{vector_db_port}\n")

    # Метаданные эмбеддингов из коллекции — для поиска используем ту же модель и text_dim
    meta = MultimodalRAG.get_embedding_meta_from_collection(vector_db_host, vector_db_port, collection_name)
    if meta:
        text_model_name = meta["text_model"]
        text_dim = meta["text_dim"]
        print(f"   Модель из метаданных коллекции: {text_model_name}, text_dim={text_dim}")
    else:
        text_model_name, text_dim = get_default_embedding_model()
        print(f"   Модель по умолчанию из конфига: {text_model_name}, text_dim={text_dim}")

    # Инициализация (без создания коллекции)
    rag = MultimodalRAG(
        vector_db_host=vector_db_host,
        vector_db_port=vector_db_port,
        collection_name=collection_name,
        text_model_name=text_model_name,
        text_dim=text_dim,
        device_text="cuda",
        device_clip="cpu",
        base_data_path=base_data_path,
    )
    # Старый вариант без учёта метаданных коллекции (могла быть рассинхронизация с load_data):
    # rag = MultimodalRAG(
    #     vector_db_host="localhost",
    #     vector_db_port="19530",
    #     collection_name="diplom_multimodal",
    #     device_text="cuda",
    #     device_clip="cpu",
    #     base_data_path="data"
    # )

    # Загрузка коллекции в память
    rag.load_collection()
    
    while True:
        print("\n" + "="*60)
        print("1. Поиск по тексту")
        print("2. Поиск по изображению")
        print("3. Гибридный поиск")
        print("4. Статистика")
        print("5. Выход")
        
        choice = input("\nВыберите режим: ")
        
        if choice == "1":
            query = input("Введите запрос: ")
            chapter = input("Глава (оставьте пустым для всех): ") or None
            results = rag.search_text(query, limit=5, filter_chapter=chapter)
            
            for i, res in enumerate(results, 1):
                print(f"\n{i}. Score: {res['score']:.4f} | Глава: {res['chapter']}")
                print(f"   {res['text'][:200]}...")
                if res['has_image']:
                    print(f"   🖼️ Изображения: {len(res['image_paths'])}")
                    for img in res['image_paths'][:3]:
                        print(f"      - {os.path.basename(img)}")
        
        elif choice == "2":
            img_path = input("Путь к изображению: ")
            if os.path.exists(img_path):
                results = rag.search_image(img_path, limit=5)
                for i, res in enumerate(results, 1):
                    print(f"\n{i}. Score: {res['score']:.4f}")
                    print(f"   {res['text'][:150]}...")
            else:
                print("❌ Файл не найден")
        
        elif choice == "3":
            query = input("Текстовый запрос: ")
            img_path = input("Путь к изображению (пусто если нет): ") or None
            results = rag.search_hybrid(query, image_path=img_path, limit=5)
            
            for i, res in enumerate(results, 1):
                print(f"\n{i}. Score: {res['score']:.4f}")
                print(f"   {res['text'][:150]}...")
        
        elif choice == "4":
            stats = rag.get_collection_stats()
            print(f"\n📊 Коллекция: {stats['name']}")
            print(f"   Сущностей: {stats['num_entities']}")
        
        elif choice == "5":
            break
    
    rag.close()
    print("\n✅ Сеанс завершен")

if __name__ == "__main__":
    main()