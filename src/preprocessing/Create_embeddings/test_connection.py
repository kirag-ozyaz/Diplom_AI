# -*- coding: utf-8 -*-
"""Проверка подключения к Milvus и списка коллекций (база default — как в RAG)."""

from pymilvus import Collection, connections, db, utility

from runtime_config import load_runtime_config


def main() -> None:
    cfg = load_runtime_config()
    vector_db = cfg["vector_db"]
    host = vector_db["host"]
    port = str(vector_db["port"])
    collection_name = vector_db["collection_name"]

    try:
        connections.connect(host=host, port=port)
        print(f" Успешное подключение к Milvus ({host}:{port})")

        databases = db.list_database()
        print(f" Базы данных: {databases}")

        # RAG-пайплайн (load_data, query) работает с базой default
        db.using_database("default")
        collections = utility.list_collections()
        print(f" Коллекции в default: {collections}")

        if collection_name in collections:
            coll = Collection(collection_name)
            coll.load()
            print(
                f" Коллекция '{collection_name}' найдена, "
                f"записей: {coll.num_entities}"
            )
        else:
            print(
                f" Коллекция '{collection_name}' не найдена в default. "
                "Если в Attu она видна — проверьте, что выбрана база default."
            )

        # Старый test_db мог остаться от прежней версии скрипта
        if "test_db" in databases:
            db.using_database("test_db")
            test_collections = utility.list_collections()
            if test_collections:
                print(f" В test_db (устаревшая тестовая БД): {test_collections}")
            else:
                print(" База test_db пуста (можно игнорировать)")

    except Exception as e:
        print(f" Ошибка подключения: {e}")


if __name__ == "__main__":
    main()
