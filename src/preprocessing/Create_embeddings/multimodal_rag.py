# -*- coding: utf-8 -*-
"""
Multimodal RAG System для диплома ИИ
Поддержка текстового и изображений векторов в Milvus
CLIP работает на CPU для экономии VRAM
"""

import os
import json
import glob
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from tqdm import tqdm

import torch
from PIL import Image
from sentence_transformers import SentenceTransformer
import open_clip

from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    MilvusException
)


class MultimodalRAG:
    """
    Класс для управления Multimodal RAG системой.
    Поддерживает загрузку текстов и изображений, векторизацию и поиск.
    """

    def __init__(
        self,
        milvus_host: str = "localhost",
        milvus_port: str = "19530",
        collection_name: str = "diplom_multimodal",
        text_model_name: str = "BAAI/bge-small-en-v1.5",
        clip_model_name: str = "ViT-B-32",
        device_text: str = "cuda",
        device_clip: str = "cpu",  # Важно для RTX 2060 6GB!
        base_data_path: str = "data"
    ):
        """
        Инициализация системы.
        
        Args:
            milvus_host: Хост Milvus
            milvus_port: Порт Milvus
            collection_name: Имя коллекции
            text_model_name: Модель для текстовых эмбедингов
            clip_model_name: Модель CLIP для изображений
            device_text: Устройство для текста (cuda/cpu)
            device_clip: Устройство для CLIP (рекомендуется cpu)
            base_data_path: Базовый путь к данным
        """
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = collection_name
        self.base_data_path = Path(base_data_path)
        
        # Размерности векторов
        self.text_dim = 384  # Для BGE-small
        self.image_dim = 512  # Для ViT-B-32
        
        # Инициализация подключений
        self._connect_milvus()
        self._load_text_model(text_model_name, device_text)
        self._load_clip_model(clip_model_name, device_clip)
        
        print("✅ MultimodalRAG инициализирован")
        print(f"   📝 Текст: {text_model_name} на {device_text}")
        print(f"   🖼️ CLIP: {clip_model_name} на {device_clip}")

    def _connect_milvus(self):
        """Подключение к Milvus"""
        try:
            connections.connect(host=self.milvus_host, port=self.milvus_port)
            print(f"✅ Подключение к Milvus: {self.milvus_host}:{self.milvus_port}")
        except Exception as e:
            raise MilvusException(f"Не удалось подключиться к Milvus: {e}")

    def _load_text_model(self, model_name: str, device: str):
        """Загрузка модели для текста"""
        print(f"📥 Загрузка текстовой модели: {model_name}")
        self.text_model = SentenceTransformer(model_name)
        self.text_device = device
        print("✅ Текстовая модель готова")

    def _load_clip_model(self, model_name: str, device: str):
        """Загрузка CLIP модели для изображений"""
        print(f"📥 Загрузка CLIP модели: {model_name}")
        # Используем open_clip для лучшей совместимости
        self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained='laion2b_e16'
        )
        self.clip_model = self.clip_model.to(device)
        self.clip_model.eval()
        self.clip_device = device
        print("✅ CLIP модель готова")

    def create_collection(self, drop_existing: bool = True):
        """
        Создание коллекции в Milvus.
        
        Args:
            drop_existing: Удалить существующую коллекцию
        """
        if utility.has_collection(self.collection_name):
            if drop_existing:
                print(f"⚠️ Коллекция '{self.collection_name}' существует. Удаляем...")
                utility.drop_collection(self.collection_name)
            else:
                print(f"✅ Коллекция '{self.collection_name}' уже существует")
                return
        
        print(f"📦 Создание коллекции '{self.collection_name}'...")
        
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="text_vector", dtype=DataType.FLOAT_VECTOR, dim=self.text_dim),
            FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=self.image_dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="image_paths", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="source_file", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="has_image", dtype=DataType.BOOL),
        ]
        
        schema = CollectionSchema(
            fields, 
            "Multimodal коллекция для диплома ИИ (текст + изображения)"
        )
        
        self.collection = Collection(self.collection_name, schema)
        
        # Создание индексов
        print("📊 Создание индексов...")
        
        # Индекс для текста
        text_index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 200}
        }
        self.collection.create_index(field_name="text_vector", index_params=text_index_params)
        
        # Индекс для изображений
        image_index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 200}
        }
        self.collection.create_index(field_name="image_vector", index_params=image_index_params)
        
        print("✅ Коллекция и индексы созданы")

    def _extract_images_from_chunk(self, chunk_text: str, chapter: str) -> List[str]:
        """
        Извлечение путей к изображениям из текста чанка.
        
        Args:
            chunk_text: Текст чанка
            chapter: Номер главы (например, "7.3")
            
        Returns:
            Список полных путей к изображениям
        """
        import re
        
        # Паттерн для поиска имен файлов изображений
        pattern = r'(img_[a-zA-Z0-9_]+\.(?:png|jpg|jpeg))'
        matches = re.findall(pattern, chunk_text)
        
        # Формируем пути к папке с изображениями
        image_folder = self.base_data_path / f"image_{chapter}"
        
        if not image_folder.exists():
            return []
        
        # Проверяем существование файлов
        valid_paths = []
        for img_name in matches:
            img_path = image_folder / img_name
            if img_path.exists():
                valid_paths.append(str(img_path))
        
        return list(set(valid_paths))  # Убираем дубликаты

    def _encode_text(self, texts: List[str]) -> List[List[float]]:
        """Векторизация текста"""
        embeddings = self.text_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()

    def _encode_image(self, image_path: str) -> List[float]:
        """
        Векторизация одного изображения (CLIP на CPU).
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Вектор изображения
        """
        try:
            image = Image.open(image_path).convert('RGB')
            image_input = self.clip_preprocess(image).unsqueeze(0).to(self.clip_device)
            
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_input)
                # Нормализация
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy()[0].tolist()
        except Exception as e:
            print(f"⚠️ Ошибка обработки изображения {image_path}: {e}")
            return [0.0] * self.image_dim

    def _encode_images_batch(self, image_paths: List[str]) -> List[List[float]]:
        """
        Векторизация нескольких изображений.
        Возвращает усредненный вектор если изображений несколько.
        
        Args:
            image_paths: Список путей к изображениям
            
        Returns:
            Вектор (усредненный если изображений > 1)
        """
        if not image_paths:
            return [0.0] * self.image_dim
        
        vectors = []
        for img_path in tqdm(image_paths, desc="   Обработка изображений", leave=False):
            vec = self._encode_image(img_path)
            vectors.append(vec)
        
        # Усреднение векторов если изображений несколько
        import numpy as np
        avg_vector = np.mean(vectors, axis=0).tolist()
        return avg_vector

    def load_from_jsonl_folder(
        self,
        jsonl_folder: str,
        batch_size: int = 32,
        skip_existing: bool = False
    ):
        """
        Загрузка данных из папки с JSONL файлами.
        
        Args:
            jsonl_folder: Путь к папке с JSONL файлами
            batch_size: Размер пакета для загрузки
            skip_existing: Пропускать существующие чанки
        """
        jsonl_path = Path(jsonl_folder)
        jsonl_files = list(jsonl_path.glob("*.jsonl"))
        
        if not jsonl_files:
            raise FileNotFoundError(f"Не найдено JSONL файлов в {jsonl_folder}")
        
        print(f"📂 Найдено файлов: {len(jsonl_files)}")
        
        total_chunks = 0
        total_images = 0
        
        for jsonl_file in jsonl_files:
            print(f"\n📄 Обработка файла: {jsonl_file.name}")
            
            # Извлекаем номер главы из имени файла (например, 7.3 из 7.3.chunked.jsonl)
            chapter = jsonl_file.stem.split('.')[0]
            
            chunks = []
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        chunks.append(json.loads(line))
            
            print(f"   Найдено чанков: {len(chunks)}")
            
            # Обработка батчами
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Извлечение текстов
                texts = [chunk.get('text', '') for chunk in batch]
                
                # Векторизация текста (GPU)
                text_vectors = self._encode_text(texts)
                
                # Обработка изображений (CPU)
                image_vectors = []
                image_paths_list = []
                has_images = []
                
                for chunk in tqdm(batch, desc=f"   Чанки {i}-{i+len(batch)}", leave=False):
                    # Извлекаем пути к изображениям
                    img_paths = self._extract_images_from_chunk(
                        chunk.get('text', ''),
                        chapter
                    )
                    
                    # Если в метаданных есть image_paths - добавляем
                    meta_images = chunk.get('metadata', {}).get('image_paths', [])
                    if meta_images:
                        for img_name in meta_images:
                            img_path = self.base_data_path / f"image_{chapter}" / img_name
                            if img_path.exists():
                                img_paths.append(str(img_path))
                    
                    img_paths = list(set(img_paths))
                    image_paths_list.append(json.dumps(img_paths, ensure_ascii=False))
                    has_images.append(len(img_paths) > 0)
                    
                    # Векторизация изображений
                    if img_paths:
                        img_vec = self._encode_images_batch(img_paths)
                        total_images += len(img_paths)
                    else:
                        img_vec = [0.0] * self.image_dim
                    
                    image_vectors.append(img_vec)
                
                # Формирование сущностей для вставки
                # Порядок полей ДОЛЖЕН совпадать с порядком в schema, за исключением auto_id-поля "id"
                # Schema: id (auto_id), chunk_id, text_vector, image_vector, text, image_paths, source_file, chapter, has_image
                entities = [
                    [
                        str(
                            chunk.get("chunk_id")
                            or chunk.get("id")
                            or f"{chapter}_{j}"
                        )
                        for j, chunk in enumerate(batch)
                    ],
                    text_vectors,
                    image_vectors,
                    [chunk.get("text", "") for chunk in batch],
                    image_paths_list,
                    [str(jsonl_file.name) for _ in batch],
                    [chapter for _ in batch],
                    has_images,
                ]
                
                # Вставка в Milvus
                self.collection.insert(entities)
                total_chunks += len(batch)
                
                if (i // batch_size) % 3 == 0:
                    print(f"   Загружено: {min(i + batch_size, len(chunks))} / {len(chunks)}")
            
            self.collection.flush()
        
        print(f"\n✅ Загрузка завершена!")
        print(f"   📊 Всего чанков: {total_chunks}")
        print(f"   🖼️ Всего изображений: {total_images}")
        print(f"   📦 Сущностей в коллекции: {self.collection.num_entities}")

    def load_collection(self):
        """Загрузка коллекции в память для поиска"""
        if not hasattr(self, 'collection'):
            self.collection = Collection(self.collection_name)
        
        self.collection.load()
        print("✅ Коллекция загружена в память")

    def search_text(
        self,
        query: str,
        limit: int = 5,
        filter_chapter: Optional[str] = None,
        with_images_only: bool = False
    ) -> List[Dict]:
        """
        Поиск по текстовому запросу.
        
        Args:
            query: Текстовый запрос
            limit: Количество результатов
            filter_chapter: Фильтр по главе (например, "7.3")
            with_images_only: Искать только чанки с изображениями
            
        Returns:
            Список результатов поиска
        """
        # Векторизация запроса
        query_vector = self.text_model.encode(
            [query],
            normalize_embeddings=True
        ).tolist()
        
        # Параметры поиска
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64}
        }
        
        # Формирование фильтра
        expr = ""
        if filter_chapter:
            expr = f"chapter == '{filter_chapter}'"
        if with_images_only:
            if expr:
                expr += " and has_image == true"
            else:
                expr = "has_image == true"
        
        # Поиск
        results = self.collection.search(
            data=[query_vector],
            anns_field="text_vector",
            param=search_params,
            limit=limit,
            expr=expr if expr else None,
            output_fields=[
                "chunk_id", "text", "image_paths", 
                "source_file", "chapter", "has_image"
            ]
        )
        
        # Форматирование результатов
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "chunk_id": hit.entity.get('chunk_id'),
                    "text": hit.entity.get('text'),
                    "image_paths": json.loads(hit.entity.get('image_paths', '[]')),
                    "source_file": hit.entity.get('source_file'),
                    "chapter": hit.entity.get('chapter'),
                    "has_image": hit.entity.get('has_image'),
                    "search_type": "text"
                })
        
        return formatted_results

    def search_image(
        self,
        image_path: str,
        limit: int = 5,
        filter_chapter: Optional[str] = None
    ) -> List[Dict]:
        """
        Поиск по изображению (image-to-image search).
        
        Args:
            image_path: Путь к изображению-запросу
            limit: Количество результатов
            filter_chapter: Фильтр по главе
            
        Returns:
            Список результатов поиска
        """
        # Векторизация изображения
        query_vector = self._encode_image(image_path)
        
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64}
        }
        
        expr = f"chapter == '{filter_chapter}'" if filter_chapter else None
        
        results = self.collection.search(
            data=[query_vector],
            anns_field="image_vector",
            param=search_params,
            limit=limit,
            expr=expr,
            output_fields=[
                "chunk_id", "text", "image_paths",
                "source_file", "chapter", "has_image"
            ]
        )
        
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "chunk_id": hit.entity.get('chunk_id'),
                    "text": hit.entity.get('text'),
                    "image_paths": json.loads(hit.entity.get('image_paths', '[]')),
                    "source_file": hit.entity.get('source_file'),
                    "chapter": hit.entity.get('chapter'),
                    "has_image": hit.entity.get('has_image'),
                    "search_type": "image"
                })
        
        return formatted_results

    def search_hybrid(
        self,
        text_query: str,
        image_path: Optional[str] = None,
        limit: int = 5,
        text_weight: float = 0.7,
        image_weight: float = 0.3
    ) -> List[Dict]:
        """
        Гибридный поиск (текст + изображение).
        
        Args:
            text_query: Текстовый запрос
            image_path: Путь к изображению (опционально)
            limit: Количество результатов
            text_weight: Вес текстового поиска (0.0-1.0)
            image_weight: Вес поиска по изображениям (0.0-1.0)
            
        Returns:
            Список результатов с комбинированным scoring
        """
        # Текстовый поиск
        text_results = self.search_text(text_query, limit=limit * 2)
        
        # Поиску по изображению (если указано)
        image_results = []
        if image_path:
            image_results = self.search_image(image_path, limit=limit * 2)
        
        # Комбинирование результатов
        from collections import defaultdict
        combined = defaultdict(lambda: {"score": 0.0, "data": None})
        
        for res in text_results:
            combined[res['id']]['score'] += res['score'] * text_weight
            combined[res['id']]['data'] = res
        
        for res in image_results:
            combined[res['id']]['score'] += res['score'] * image_weight
            if not combined[res['id']]['data']:
                combined[res['id']]['data'] = res
        
        # Сортировка по итоговому score
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:limit]
        
        return [item['data'] for item in sorted_results]

    def get_collection_stats(self) -> Dict:
        """Получение статистики коллекции"""
        if not hasattr(self, 'collection'):
            self.collection = Collection(self.collection_name)
        
        return {
            "name": self.collection.name,
            "num_entities": self.collection.num_entities,
            "schema": [f.name for f in self.collection.schema.fields],
            "indexes": [idx.field_name for idx in self.collection.indexes]
        }

    def close(self):
        """Закрытие соединения с Milvus"""
        connections.disconnect("default")
        print("🔌 Соединение с Milvus закрыто")