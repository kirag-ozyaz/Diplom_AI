# -*- coding: utf-8 -*-
"""Текстовый поиск по коллекции diplom_multimodal_e5 (префикс query:).

Запуск из корня проекта:
  python src/preprocessing/Create_embeddings/E5/query_e5.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e5_rag import open_text_rag


def main() -> None:
    print(" Поиск по коллекции E5 (query:)...")
    rag, cfg = open_text_rag()
    limit = int(cfg["query"]["default_limit"])
    print(f" Коллекция: {rag.collection_name}, limit={limit}")

    while True:
        print("\n" + "=" * 60)
        print("1. Поиск по тексту")
        print("2. Статистика")
        print("3. Выход")
        choice = input("\nВыберите режим: ").strip()

        if choice == "1":
            query = input("Введите запрос: ").strip()
            if not query:
                print(" Пустой запрос")
                continue
            chapter = input("Глава (пусто — без фильтра): ").strip() or None
            results = rag.search_text(query, limit=limit, filter_chapter=chapter)
            if not results:
                print(" Ничего не найдено")
                continue
            for i, res in enumerate(results, 1):
                print(f"\n{i}. Score: {res['score']:.4f} | Глава: {res['chapter']}")
                text = res.get("text") or ""
                print(f"   {text[:200]}...")
        elif choice == "2":
            stats = rag.get_collection_stats()
            print(f"\n Коллекция: {stats['name']}")
            print(f"   Сущностей: {stats['num_entities']}")
        elif choice == "3":
            break

    rag.close()
    print("\n Сеанс завершен")


if __name__ == "__main__":
    main()
