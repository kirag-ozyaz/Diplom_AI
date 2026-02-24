from pymilvus import connections, utility, db

try:
    # Подключение к локальному Milvus
    connections.connect(host="localhost", port="19530")
    print("✅ Успешное подключение к Milvus!")

    if "test_db" not in db.list_database():
        db.create_database("test_db")

    db.using_database("test_db")

    # 2. Работа с Коллекцией (Collection)
    # Теперь коллекция создается внутри выбранной БД
    if not utility.has_collection("diplom_rag"):
        # ... создание схемы и коллекции ...
        pass

    # Проверка списка коллекций
    collections = utility.list_collections()
    print(f"📦 Существующие коллекции: {collections}")
    
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")