# -*- coding: utf-8 -*-
"""
Multimodal RAG System для диплома ИИ
Поддержка текстовых и изображений векторов в векторной БД
CLIP работает на CPU для экономии VRAM
"""

import os
import sys
import json
import glob
import socket
from typing import List, Dict, Optional, Tuple, Any, Union
from pathlib import Path
from tqdm import tqdm
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

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

# Путь к конфигу «модель → размерность» (рядом с multimodal_rag.py)
_EMBEDDING_CONFIG_PATH = Path(__file__).resolve().parent / "embedding_config.json"


def _load_embedding_config() -> Optional[Dict[str, Any]]:
    """Читает embedding_config.json. Возвращает None при ошибке или отсутствии файла."""
    if not _EMBEDDING_CONFIG_PATH.exists():
        return None
    try:
        with open(_EMBEDDING_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def _get_text_dim_from_config(text_model_name: str) -> int:
    """
    Возвращает text_dim для модели из embedding_config.json.
    Если модели нет в конфиге — используется default_dim из конфига или 384.
    """
    data = _load_embedding_config()
    if not data:
        return 384
    mapping = data.get("text_model_dim") or {}
    if text_model_name in mapping:
        return int(mapping[text_model_name])
    return int(data.get("default_dim", 384))


def get_default_embedding_model() -> Tuple[str, int]:
    """
    Возвращает (default_text_model, text_dim) из embedding_config.json.
    Используется, когда метаданные коллекции недоступны (query/query_test).
    """
    data = _load_embedding_config()
    if not data:
        return ("BAAI/bge-small-en-v1.5", 384)
    model = data.get("default_text_model") or "BAAI/bge-small-en-v1.5"
    dim = _get_text_dim_from_config(model)
    return (model, dim)


class MultimodalRAG:
    """
    Класс для управления Multimodal RAG системой.
    Поддерживает загрузку текстов и изображений, векторизацию и поиск.
    """

    def __init__(
        self,
        vector_db_host: str = "localhost",
        vector_db_port: str = "19530",
        collection_name: str = "diplom_multimodal",
        text_model_name: str = "BAAI/bge-small-en-v1.5",  
        # альт.: "sentence-transformers/all-MiniLM-L6-v2" (легче, 384 dim)
        clip_model_name: str = "ViT-B-32",
        device_text: str = "cuda",
        device_clip: str = "cpu",  # Важно для RTX 2060 6GB!
        base_data_path: str = "data",
        image_encode_workers: int = 4,
        batch_chunk_workers: int = 2,
        load_image_model: bool = True,
        text_dim: Optional[int] = None,
    ):
        """
        Инициализация системы.

        Args:
            vector_db_host: Хост векторной БД
            vector_db_port: Порт векторной БД
            collection_name: Имя коллекции
            text_model_name: Модель для текстовых эмбедингов
            clip_model_name: Модель CLIP для изображений
            device_text: Устройство для текста (cuda/cpu)
            device_clip: Устройство для CLIP (рекомендуется cpu)
            base_data_path: Базовый путь к данным
            image_encode_workers: Потоков для кодирования изображений (0 или 1 = последовательно)
            batch_chunk_workers: Потоков для параллельной обработки чанков в батче (0 = последовательно)
            load_image_model: Загружать ли CLIP (False — только текстовый поиск по готовой коллекции)
            text_dim: Размерность текстового эмбеддинга. Если None — берётся из embedding_config.json по text_model_name.
        """
        self.vector_db_host = vector_db_host
        self.vector_db_port = vector_db_port
        self.collection_name = collection_name
        self._text_model_name = text_model_name  # для метаданных коллекции и проверки при поиске
        self.base_data_path = Path(base_data_path)
        self.image_encode_workers = max(0, image_encode_workers)
        self.batch_chunk_workers = max(0, batch_chunk_workers)
        self._load_image_model = load_image_model
        self._clip_model_name = clip_model_name
        self._device_clip = device_clip
        
        # Размерности векторов (text_dim из аргумента или из embedding_config.json по text_model_name)
        if text_dim is not None:
            self.text_dim = text_dim
        else:
            self.text_dim = _get_text_dim_from_config(text_model_name)
        self.image_dim = 512  # Для ViT-B-32
        # Таблица текстовых моделей (RAM 64Gb, RTX 2060 6Gb). При смене dim — пересоздать коллекцию.
        # --------------------------------------------------------------------------------------------
        # Модель                                    | dim  | Память   | Замечание
        # ------------------------------------------|------|----------|------------------------------
        # BAAI/bge-small-en-v1.5                     | 384  | ~400 MB  | по умолчанию, баланс качества
        # sentence-transformers/all-MiniLM-L6-v2      | 384  | ~90 MB   | легче и быстрее
        # sentence-transformers/paraphrase-MiniLM-L3-v2 | 384 | ~60 MB  | ещё легче
        # BAAI/bge-base-en-v1.5                      | 768  | ~450 MB  | лучше качество, text_dim=768
        # sentence-transformers/all-mpnet-base-v2    | 768  | ~420 MB  | text_dim=768
        # BAAI/bge-large-en-v1.5                     | 1024 | ~1.3 GB  | макс. качество, text_dim=1024
        # --------------------------------------------------------------------------------------------

        # ВАЖНЫЕ ПРИМЕЧАНИЯ ПО ВЫБОРУ МОДЕЛИ:
        # 1. Max tokens: У разных моделей разный максимум токенов на один документ.
        #    - MiniLM, bge-small: 512 токенов
        #    - bge-m3, nomic-embed: 8192 токенов (можно слать целые страницы)
        #    - jina-embeddings-v3: 8192 токенов
        #    - multilingual-e5-base: 512 токенов
        #
        # 2. Normalization: Большинство новых моделей требуют нормализации векторов.
        #    Добавьте в код: embeddings = model.encode(docs) 
        #                     normalized = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        #
        # 3. Query instruction: Некоторые модели (bge, e5) требуют специальных префиксов:
        #    - Для BGE: query = f"Represent this sentence for searching relevant passages: {query}"
        #    - Для E5: query = f"query: {query}", passage = f"passage: {text}"
        #    - Для mxbai: query = f"Represent this query for retrieving documents: {query}"
        #    - Для jina-embeddings-v3: query = model.encode([query], task="retrieval.query")
        #                               doc = model.encode([text], task="retrieval.passage")
        #
        # 4. Метрика расстояния: Для нормализованных векторов используйте COSINE, для ненормализованных - IP
        #
        # 5. Размерность (dim): При смене модели с другой размерностью необходимо пересоздать коллекцию в векторной БД

        # Таблица текстовых эмбеддинговых моделей (RAM 64Gb, RTX 2060 6Gb)
        # --------------------------------------------------------------------------------------------------------------------
        # Модель                                    | dim  | Память   | Скорость | Язык     | Особенность
        # ------------------------------------------|------|----------|----------|----------|--------------------------------
        # Базовые модели (легкие и быстрые)
        # ------------------------------------------|------|----------|----------|----------|--------------------------------
        # sentence-transformers/paraphrase-MiniLM-L3-v2 | 384 | ~60 MB   | +++++ | Мульти  | Максимально легкая, базовая
        # sentence-transformers/all-MiniLM-L6-v2      | 384  | ~90 MB   | ++++ | EN       | Легче и быстрее
        # BAAI/bge-small-en-v1.5                     | 384  | ~400 MB  | +++   | EN       | По умолчанию, баланс качества
        # intfloat/e5-small-v2                        | 384  | ~450 MB  | +++   | EN       | Специализация на retrieval
        # Cohere/embed-multilingual-light-v3.0        | 384  | ~300 MB  | +++   | Мульти  | Легкая мультиязычная (API или локально)
        # 
        # Модели среднего размера (оптимальный баланс)
        # ------------------------------------------|------|----------|----------|----------|--------------------------------
        # BAAI/bge-base-en-v1.5                      | 768  | ~450 MB  | ++     | EN       | Лучше качество, text_dim=768
        # sentence-transformers/all-mpnet-base-v2     | 768  | ~420 MB  | ++    | EN       | Хороший баланс скорость/качество
        # intfloat/e5-base-v2                         | 768  | ~500 MB  | ++     | EN       | Высокое качество для поиска
        # Alibaba-NLP/gte-base-en-v1.5                | 768  | ~450 MB  | ++     | EN       | SOTA для retrieval (2024)
        # nomic-embed-text-v1.5                       | 768  | ~550 MB  | ++     | EN/Мульти| Поддержка длинного контекста (8192)
        # intfloat/multilingual-e5-base                | 768  | ~1.1 GB  | ++     | Мульти  | Отличное качество для русского и английского
        # 
        # Крупные модели (максимальное качество)
        # ------------------------------------------|------|----------|----------|----------|--------------------------------
        # mixedbread-ai/mxbai-embed-large-v1          | 1024 | ~670 MB  | ++     | EN       | SOTA для RAG, trainable prefix
        # BAAI/bge-large-en-v1.5                      | 1024 | ~1.3 GB  | +       | EN       | Макс. качество для английского
        # BAAI/bge-m3                                  | 1024 | ~2.2 GB  | +       | Мульти  | Поддержка 100+ языков, dense/sparse, длинные тексты
        # jina-embeddings-v3                          | 1024 | ~1.1 GB  | ++     | Мульти  | 512/768/1024 dim, поддержка 8192 токенов
        # 
        # Реранкеры (используются после основного поиска для переранжирования)
        # ------------------------------------------|------|----------|----------|----------|--------------------------------
        # BAAI/bge-reranker-v2-m3                      | -    | ~2.5 GB  | -       | Мульти  | Реранкер (отдельный этап после поиска)
        # 
        # Модели, которые НЕ влезут в VRAM (для справки)
        # ------------------------------------------|------|----------|----------|----------|--------------------------------
        # intfloat/e5-mistral-7b-instruct              | 4096 | ~15 GB   | ---   | EN       | ❌ Не влезет в 6GB VRAM
        # --------------------------------------------------------------------------------------------------------------------

        # Рекомендации по выбору под задачу:
        # -----------------------------------
        # Для первоначального тестирования выбираем:
        # BAAI/bge-small-en-v1.5 (dim 384)
        # sentence-transformers/all-MiniLM-L6-v2 (dim 384)
        # BAAI/bge-m3 (dim 1024)
        # intfloat/multilingual-e5-base (dim 768? хороший русский язык)
        #
        # Для английских документов, максимум качества:     BAAI/bge-large-en-v1.5 или mixedbread-ai/mxbai-embed-large-v1
        # Для английских документов, баланс:                BAAI/bge-base-en-v1.5 или intfloat/e5-base-v2
        # Для английских документов, максимальная скорость:  sentence-transformers/all-MiniLM-L6-v2
        #
        # Для мультиязычных (русский + английский), качество:  intfloat/multilingual-e5-base или BAAI/bge-m3
        # Для мультиязычных (русский + английский), скорость:   Cohere/embed-multilingual-light-v3.0
        #
        # Для очень длинных документов (целые страницы):       nomic-embed-text-v1.5 или jina-embeddings-v3 или BAAI/bge-m3
        #
        # Если нужен реранкинг для максимальной точности:      BAAI/bge-reranker-v2-m3 (использовать ТОЛЬКО после основного поиска)
       
        # Инициализация подключений
        self._connect_vector_db()
        self._load_text_model(text_model_name, device_text)
        if load_image_model:
            self._load_clip_model(clip_model_name, device_clip)
        else:
            self.clip_model = None
            self.clip_preprocess = None
            self.clip_device = None
            print("ℹ️ CLIP не загружается (режим только текстового поиска)")
        
        print("✅ MultimodalRAG инициализирован")
        print(f"   📝 Текст: {text_model_name} на {device_text}")
        if load_image_model:
            print(f"   🖼️ CLIP: {clip_model_name} на {device_clip}")

    @staticmethod
    def _check_vector_db_available(host: str, port: str, timeout: float = 2.0) -> bool:
        """Проверяет, доступен ли сервер векторной БД по указанному хосту и порту."""
        try:
            port_int = int(port)
            with socket.create_connection((host, port_int), timeout=timeout):
                return True
        except (socket.timeout, socket.error, OSError, ValueError):
            return False

    @staticmethod
    def check_vector_db_server(
        host: str = "localhost",
        port: Union[str, int] = 19530,
        timeout: float = 2.0,
    ) -> bool:
        """
        Проверяет, доступен ли сервер векторной БД по указанному хосту и порту.
        Общий метод для скриптов (query, query_test, load_data и т.д.).
        port может быть строкой или числом.
        """
        return MultimodalRAG._check_vector_db_available(host, str(port), timeout)

    def _connect_vector_db(self):
        """Подключение к векторной БД. При недоступности сервера — сообщение и завершение процесса."""
        if not self._check_vector_db_available(self.vector_db_host, self.vector_db_port):
            print(
                f"❌ Векторная БД недоступна: {self.vector_db_host}:{self.vector_db_port}\n"
                "   Убедитесь, что сервер запущен (например, через docker-compose), и повторите попытку."
            )
            sys.exit(1)
        try:
            connections.connect(host=self.vector_db_host, port=self.vector_db_port)
            print(f"✅ Подключение к векторной БД: {self.vector_db_host}:{self.vector_db_port}")
        except Exception as e:
            print(
                f"❌ Не удалось подключиться к векторной БД: {e}\n"
                "   Проверьте, что сервер запущен и параметры подключения верны."
            )
            sys.exit(1)

    def _load_text_model(self, model_name: str, device: str):
        """Загрузка модели для текста"""
        print(f"📥 Загрузка текстовой модели: {model_name}")
        # Показываем прогресс скачивания (в процентах) при первом запуске.
        # HuggingFace Hub сам рисует tqdm progress-bar в консоли.
        try:
            from huggingface_hub import snapshot_download
            print("   ⬇️ Проверка/скачивание файлов модели (HuggingFace cache)...")
            snapshot_download(
                repo_id=model_name,
                resume_download=True,
            )
            print("   ✅ Файлы текстовой модели готовы (в кэше)")
        except Exception as e:
            # Если huggingface_hub недоступен или нет интернета — просто продолжаем,
            # SentenceTransformer сам попробует загрузить/взять из кэша.
            print(f"   ⚠️ Не удалось показать прогресс скачивания для текста: {e}")

        self.text_model = SentenceTransformer(model_name)
        self.text_device = device
        print("✅ Текстовая модель готова")

    def _load_clip_model(self, model_name: str, device: str):
        """Загрузка CLIP модели для изображений"""
        print(f"📥 Загрузка CLIP модели: {model_name}")
        # Пытаемся предзагрузить веса CLIP с прогресс-баром (если open_clip знает HF repo).
        try:
            from huggingface_hub import snapshot_download

            # open_clip хранит метаданные о pretrained весах; часть из них лежит на HF Hub.
            # Если hf_hub_id отсутствует, прогресс показать не получится — тогда просто загрузим как обычно.
            cfg = open_clip.get_pretrained_cfg(model_name, pretrained='laion2b_e16') or {}
            hf_id = cfg.get("hf_hub_id") or cfg.get("hf_hub") or cfg.get("repo_id")
            if hf_id:
                print(f"   ⬇️ Проверка/скачивание CLIP весов (HuggingFace): {hf_id}")
                snapshot_download(
                    repo_id=hf_id,
                    resume_download=True,
                )
                print("   ✅ Файлы CLIP готовы (в кэше)")
            else:
                print("   ℹ️ open_clip не дал hf_hub_id для этих весов — загрузка будет без процентов")
        except Exception as e:
            print(f"   ⚠️ Не удалось показать прогресс скачивания для CLIP: {e}")

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
        Создание коллекции в векторной БД.
        
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
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="text_vector", dtype=DataType.FLOAT_VECTOR, dim=self.text_dim),
            FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=self.image_dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="image_paths", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="source_file", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="has_image", dtype=DataType.BOOL),
        ]
        
        desc = (
            "Multimodal коллекция для диплома ИИ (текст + изображения). "
            f"text_model={self._text_model_name}, text_dim={self.text_dim}"
        )
        schema = CollectionSchema(fields, desc)
        
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

    def _extract_images_from_chunk(
        self,
        chunk_text: str,
        chapter: str,
        base_dir: Optional[Path] = None
    ) -> List[str]:
        """
        Извлечение путей к изображениям из текста чанка.
        
        Args:
            chunk_text: Текст чанка
            chapter: Номер главы (например, "7.3")
            base_dir: Базовая директория, относительно которой резолвим относительные пути
            
        Returns:
            Список полных путей к изображениям
        """
        import re

        if not chunk_text:
            return []

        base_dir = Path(base_dir) if base_dir is not None else self.base_data_path

        # 1) Markdown-картинки: ![alt](path "title")
        md_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
        # 2) HTML img
        html_pattern = r'<img[^>]+src=[\'"]([^\'"]+)[\'"]'
        # 3) Фоллбек: любая "похожая на путь" строка с расширением картинки
        any_img_pattern = r'([^\s\)\]]+\.(?:png|jpg|jpeg|gif|webp))'

        refs: List[str] = []
        refs.extend(re.findall(md_pattern, chunk_text, flags=re.IGNORECASE))
        refs.extend(re.findall(html_pattern, chunk_text, flags=re.IGNORECASE))
        if not refs:
            refs.extend(re.findall(any_img_pattern, chunk_text, flags=re.IGNORECASE))

        def _clean_ref(r: str) -> str:
            r = r.strip().strip("<>").strip().strip('"').strip("'")
            # если есть title после пробела — берём только путь
            r = r.split()[0] if r else r
            return r

        def _is_url(r: str) -> bool:
            rl = r.lower()
            return rl.startswith("http://") or rl.startswith("https://") or rl.startswith("data:")

        def _candidate_paths(ref: str) -> List[Path]:
            # Нормализуем разделители
            ref_norm = ref.replace("\\", "/")
            p = Path(ref_norm)

            candidates: List[Path] = []
            if p.is_absolute():
                candidates.append(p)
                return candidates

            # Основной кейс: JSONL и папки image_* лежат рядом
            candidates.append(base_dir / p)

            # Кейс, когда в тексте только имя файла без папки
            candidates.append(base_dir / f"image_{chapter}" / p)

            # Фоллбек на self.base_data_path (если base_dir отличается)
            if base_dir != self.base_data_path:
                candidates.append(self.base_data_path / p)
                candidates.append(self.base_data_path / f"image_{chapter}" / p)

            return candidates

        valid_paths: List[str] = []
        for raw in refs:
            ref = _clean_ref(raw)
            if not ref or _is_url(ref):
                continue

            for cand in _candidate_paths(ref):
                try:
                    if cand.exists() and cand.is_file():
                        valid_paths.append(str(cand.resolve()))
                        break
                except OSError:
                    # на случай некорректных символов в пути
                    continue

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
        if self.clip_model is None:
            raise RuntimeError(
                "Модель изображений (CLIP) не загружена. Создайте MultimodalRAG с load_image_model=True для поиска по изображениям."
            )
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
        Векторизация нескольких изображений (с распараллеливанием по потокам).
        Возвращает усредненный вектор если изображений несколько.
        
        Args:
            image_paths: Список путей к изображениям
            
        Returns:
            Вектор (усредненный если изображений > 1)
        """
        if not image_paths:
            return [0.0] * self.image_dim
        if self.clip_model is None:
            raise RuntimeError(
                "Модель изображений (CLIP) не загружена. Создайте MultimodalRAG с load_image_model=True для поиска по изображениям."
            )
        
        import numpy as np
        if self.image_encode_workers <= 1:
            vectors = []
            for img_path in tqdm(image_paths, desc="   Обработка изображений", leave=False):
                vectors.append(self._encode_image(img_path))
        else:
            with ThreadPoolExecutor(max_workers=self.image_encode_workers) as ex:
                vectors = list(tqdm(
                    ex.map(self._encode_image, image_paths),
                    total=len(image_paths),
                    desc="   Обработка изображений",
                    leave=False,
                ))
        
        avg_vector = np.mean(vectors, axis=0).tolist()
        return avg_vector

    def load_from_jsonl_folder(
        self,
        jsonl_folder: str,
        batch_size: int = 32,
        skip_existing: bool = False,
        log_every_batches: int = 3,
        log_file_summary: bool = True
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
            file_t0 = time.time()
            print(f"\n📄 Обработка файла: {jsonl_file.name}")
            
            # Извлекаем номер главы из имени файла (например, 7.3 из 7.3.chunked.jsonl)
            if jsonl_file.name.endswith(".chunked.jsonl"):
                chapter = jsonl_file.name[: -len(".chunked.jsonl")]
            else:
                chapter = jsonl_file.stem
            
            chunks = []
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        chunks.append(json.loads(line))
            
            print(f"   Найдено чанков: {len(chunks)}")
            if log_file_summary:
                num_batches = (len(chunks) + batch_size - 1) // batch_size if chunks else 0
                print(f"   Глава: {chapter} | Батчей: {num_batches} | batch_size: {batch_size}")
            
            # Обработка батчами
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Извлечение текстов
                texts = [(chunk.get('text') or chunk.get('content') or '') for chunk in batch]
                
                # Векторизация текста (GPU)
                text_vectors = self._encode_text(texts)
                
                # Обработка изображений (CPU): сначала собираем пути по чанкам, затем векторизуем (с опцией параллелизма)
                image_paths_list = []
                has_images = []
                chunk_image_paths = []
                for chunk in batch:
                    img_paths = self._extract_images_from_chunk(
                        chunk.get('text') or chunk.get('content') or '',
                        chapter,
                        base_dir=jsonl_file.parent
                    )
                    meta_images = (
                        chunk.get('metadata', {}).get('image_paths', [])
                        or chunk.get('image_paths', [])
                    )
                    if meta_images:
                        for img_name in meta_images:
                            meta_found = self._extract_images_from_chunk(
                                str(img_name),
                                chapter,
                                base_dir=jsonl_file.parent
                            )
                            img_paths.extend(meta_found)
                    img_paths = list(set(img_paths))
                    chunk_image_paths.append(img_paths)
                    image_paths_list.append(json.dumps(img_paths, ensure_ascii=False))
                    has_images.append(len(img_paths) > 0)
                batch_images = sum(len(p) for p in chunk_image_paths)
                total_images += batch_images

                def _encode_chunk_images(paths: List[str]) -> List[float]:
                    if paths:
                        return self._encode_images_batch(paths)
                    return [0.0] * self.image_dim

                if self.batch_chunk_workers > 1:
                    with ThreadPoolExecutor(max_workers=self.batch_chunk_workers) as ex:
                        image_vectors = list(tqdm(
                            ex.map(_encode_chunk_images, chunk_image_paths),
                            total=len(chunk_image_paths),
                            desc=f"   Чанки {i}-{i+len(batch)}",
                            leave=False,
                        ))
                else:
                    image_vectors = [
                        _encode_chunk_images(paths)
                        for paths in tqdm(chunk_image_paths, desc=f"   Чанки {i}-{i+len(batch)}", leave=False)
                    ]
                
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
                    [(chunk.get("text") or chunk.get("content") or "") for chunk in batch],
                    image_paths_list,
                    [str(jsonl_file.name) for _ in batch],
                    [chapter for _ in batch],
                    has_images,
                ]
                
                # Вставка в векторную БД
                self.collection.insert(entities)
                total_chunks += len(batch)
                
                if log_every_batches and ((i // batch_size) % log_every_batches == 0):
                    batch_no = (i // batch_size) + 1
                    total_batches = (len(chunks) + batch_size - 1) // batch_size
                    print(
                        f"   [{jsonl_file.name}] батч {batch_no}/{total_batches}: "
                        f"вставлено {len(batch)} | картинок в батче {batch_images} | "
                        f"прогресс {min(i + batch_size, len(chunks))}/{len(chunks)}"
                    )
            
            self.collection.flush()
            if log_file_summary:
                dt = time.time() - file_t0
                try:
                    ents = self.collection.num_entities
                except Exception:
                    ents = "?"
                print(f"✅ Файл завершён: {jsonl_file.name} | time={dt:.1f}s | сущностей в коллекции={ents}")
        
        print(f"\n✅ Загрузка завершена!")
        print(f"   📊 Всего чанков: {total_chunks}")
        print(f"   🖼️ Всего изображений: {total_images}")
        print(f"   📦 Сущностей в коллекции: {self.collection.num_entities}")

    async def load_from_jsonl_folder_async(
        self,
        jsonl_folder: str,
        batch_size: int = 32,
        skip_existing: bool = False,
        yield_every_batches: int = 1,
        log_every_batches: int = 3,
        log_file_summary: bool = True,
    ):
        """
        Асинхронная версия загрузки.
        
        Клиент вставляет данные синхронно, поэтому insert/flush выполняются
        в worker-thread через asyncio.to_thread, чтобы не блокировать event loop.
        
        Args:
            jsonl_folder: Путь к папке с JSONL файлами
            batch_size: Размер пакета для загрузки
            skip_existing: (пока не реализовано) пропуск существующих чанков
            yield_every_batches: как часто отдавать управление loop (для отзывчивости)
        """
        # Переиспользуем синхронную реализацию, но самые блокирующие операции с БД
        # выносим в отдельный поток. Это удобно, если вы запускаете загрузку параллельно
        # с чем-то ещё (бот/UI/прогресс) в одном процессе.

        jsonl_path = Path(jsonl_folder)
        jsonl_files = list(jsonl_path.glob("*.jsonl"))

        if not jsonl_files:
            raise FileNotFoundError(f"Не найдено JSONL файлов в {jsonl_folder}")

        print(f"📂 Найдено файлов: {len(jsonl_files)}")

        total_chunks = 0
        total_images = 0
        batch_counter = 0

        for jsonl_file in jsonl_files:
            file_t0 = time.time()
            print(f"\n📄 Обработка файла: {jsonl_file.name}")

            # Извлекаем номер главы из имени файла (например, 7.3 из 7.3.chunked.jsonl)
            if jsonl_file.name.endswith(".chunked.jsonl"):
                chapter = jsonl_file.name[: -len(".chunked.jsonl")]
            else:
                chapter = jsonl_file.stem

            # Чтение файла — IO, поэтому можно в thread
            def _read_chunks():
                chunks_local = []
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            chunks_local.append(json.loads(line))
                return chunks_local

            chunks = await asyncio.to_thread(_read_chunks)
            print(f"   Найдено чанков: {len(chunks)}")
            if log_file_summary:
                num_batches = (len(chunks) + batch_size - 1) // batch_size if chunks else 0
                print(f"   Глава: {chapter} | Батчей: {num_batches} | batch_size: {batch_size}")

            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]

                # Извлечение текстов + текстовые эмбеддинги (torch) — оставляем синхронно
                # (обычно это самый быстрый путь и без лишней многопоточности на GPU)
                texts = [(chunk.get('text') or chunk.get('content') or '') for chunk in batch]
                text_vectors = self._encode_text(texts)

                # Изображения (CPU): собираем пути по чанкам, затем векторизуем (с опцией параллелизма)
                image_paths_list = []
                has_images = []
                chunk_image_paths = []
                for chunk in batch:
                    img_paths = self._extract_images_from_chunk(
                        chunk.get('text') or chunk.get('content') or '',
                        chapter,
                        base_dir=jsonl_file.parent
                    )
                    meta_images = (
                        chunk.get('metadata', {}).get('image_paths', [])
                        or chunk.get('image_paths', [])
                    )
                    if meta_images:
                        for img_name in meta_images:
                            meta_found = self._extract_images_from_chunk(
                                str(img_name),
                                chapter,
                                base_dir=jsonl_file.parent
                            )
                            img_paths.extend(meta_found)
                    img_paths = list(set(img_paths))
                    chunk_image_paths.append(img_paths)
                    image_paths_list.append(json.dumps(img_paths, ensure_ascii=False))
                    has_images.append(len(img_paths) > 0)
                batch_images = sum(len(p) for p in chunk_image_paths)
                total_images += batch_images

                def _encode_chunk_images_async(paths: List[str]) -> List[float]:
                    if paths:
                        return self._encode_images_batch(paths)
                    return [0.0] * self.image_dim

                if self.batch_chunk_workers > 1:
                    with ThreadPoolExecutor(max_workers=self.batch_chunk_workers) as ex:
                        image_vectors = list(tqdm(
                            ex.map(_encode_chunk_images_async, chunk_image_paths),
                            total=len(chunk_image_paths),
                            desc=f"   Чанки {i}-{i+len(batch)}",
                            leave=False,
                        ))
                else:
                    image_vectors = [
                        _encode_chunk_images_async(paths)
                        for paths in tqdm(chunk_image_paths, desc=f"   Чанки {i}-{i+len(batch)}", leave=False)
                    ]

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
                    [(chunk.get("text") or chunk.get("content") or "") for chunk in batch],
                    image_paths_list,
                    [str(jsonl_file.name) for _ in batch],
                    [chapter for _ in batch],
                    has_images,
                ]

                # Вставка в векторную БД — в thread
                await asyncio.to_thread(self.collection.insert, entities)
                total_chunks += len(batch)

                if log_every_batches and ((i // batch_size) % log_every_batches == 0):
                    batch_no = (i // batch_size) + 1
                    total_batches = (len(chunks) + batch_size - 1) // batch_size
                    print(
                        f"   [{jsonl_file.name}] батч {batch_no}/{total_batches}: "
                        f"вставлено {len(batch)} | картинок в батче {batch_images} | "
                        f"прогресс {min(i + batch_size, len(chunks))}/{len(chunks)}"
                    )

                batch_counter += 1
                if yield_every_batches and (batch_counter % yield_every_batches == 0):
                    await asyncio.sleep(0)  # отдаём управление loop

            await asyncio.to_thread(self.collection.flush)
            if log_file_summary:
                dt = time.time() - file_t0
                try:
                    ents = self.collection.num_entities
                except Exception:
                    ents = "?"
                print(f"✅ Файл завершён: {jsonl_file.name} | time={dt:.1f}s | сущностей в коллекции={ents}")

        print(f"\n✅ Загрузка завершена!")
        print(f"   📊 Всего чанков: {total_chunks}")
        print(f"   🖼️ Всего изображений: {total_images}")
        print(f"   📦 Сущностей в коллекции: {self.collection.num_entities}")

    @staticmethod
    def _parse_embedding_meta(description: str) -> Optional[Dict[str, Any]]:
        """Извлекает text_model и text_dim из описания коллекции (метаданные эмбеддингов)."""
        if not description:
            return None
        import re
        m = re.search(r"text_model=([^,]+),\s*text_dim=(\d+)", description)
        if not m:
            return None
        return {"text_model": m.group(1).strip(), "text_dim": int(m.group(2))}

    def get_collection_embedding_meta(self) -> Optional[Dict[str, Any]]:
        """Возвращает метаданные эмбеддингов коллекции (text_model, text_dim), если записаны."""
        if not hasattr(self, "collection"):
            self.collection = Collection(self.collection_name)
        info = self.collection.describe()
        desc = info.get("description") or ""
        return self._parse_embedding_meta(desc)

    @classmethod
    def get_embedding_meta_from_collection(
        cls, vector_db_host: str, vector_db_port: str, collection_name: str
    ) -> Optional[Dict[str, Any]]:
        """Подключение к векторной БД и чтение метаданных эмбеддингов из описания коллекции (без создания RAG)."""
        if not cls._check_vector_db_available(vector_db_host, vector_db_port):
            print(
                f"❌ Векторная БД недоступна: {vector_db_host}:{vector_db_port}\n"
                "   Убедитесь, что сервер запущен (например, через docker-compose), и повторите попытку."
            )
            sys.exit(1)
        try:
            connections.connect(host=vector_db_host, port=vector_db_port)
        except Exception as e:
            print(
                f"❌ Не удалось подключиться к векторной БД: {e}\n"
                "   Проверьте, что сервер запущен и параметры подключения верны."
            )
            sys.exit(1)
        if not utility.has_collection(collection_name):
            return None
        c = Collection(collection_name)
        info = c.describe()
        return cls._parse_embedding_meta(info.get("description") or "")

    def load_collection(self):
        """Загрузка коллекции в память для поиска"""
        if not hasattr(self, 'collection'):
            self.collection = Collection(self.collection_name)

        info = self.collection.describe()
        meta = self._parse_embedding_meta(info.get("description") or "")
        if meta:
            if meta.get("text_dim") != self.text_dim:
                print(
                    f"⚠️ Внимание: коллекция создана с text_dim={meta['text_dim']}, "
                    f"сейчас задано {self.text_dim}. Поиск может сломаться — используйте ту же модель и text_dim."
                )
            if meta.get("text_model") != self._text_model_name:
                print(
                    f"⚠️ Внимание: коллекция создана с text_model={meta['text_model']}, "
                    f"сейчас задано {self._text_model_name}. Нужна та же модель для корректного поиска."
                )

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
            query,
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

        def _get(hit, field: str, default=None):
            """Получить поле из hit (поддержка hit.get и hit.entity.get)."""
            if hasattr(hit, 'get') and callable(hit.get):
                v = hit.get(field)
                if v is not None:
                    return v
            if hasattr(hit, 'entity') and hit.entity is not None:
                return hit.entity.get(field, default)
            return default

        # Форматирование результатов
        formatted_results = []
        for hits in results:
            for hit in hits:
                text_val = _get(hit, 'text') or ''
                image_paths_raw = _get(hit, 'image_paths') or '[]'
                formatted_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "chunk_id": _get(hit, 'chunk_id'),
                    "text": text_val if isinstance(text_val, str) else str(text_val),
                    "image_paths": json.loads(image_paths_raw) if isinstance(image_paths_raw, str) else (image_paths_raw or []),
                    "source_file": _get(hit, 'source_file'),
                    "chapter": _get(hit, 'chapter'),
                    "has_image": _get(hit, 'has_image'),
                    "search_type": "text"
                })

        # Если текст пустой — векторная БД иногда не возвращает длинные VARCHAR в search; догружаем через query
        need_text_ids = [r["id"] for r in formatted_results if not (r.get("text") or "").strip()]
        if need_text_ids:
            try:
                q = self.collection.query(
                    expr=f"id in {need_text_ids}",
                    output_fields=["id", "text"]
                )
                id_to_text = {row["id"]: (row.get("text") or "") for row in q}
                for r in formatted_results:
                    if not (r.get("text") or "").strip() and r["id"] in id_to_text:
                        r["text"] = id_to_text[r["id"]] or ""
            except Exception as e:
                print(f"⚠️ Не удалось догрузить текст по id: {e}")

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

        def _get(hit, field: str, default=None):
            if hasattr(hit, 'get') and callable(hit.get):
                v = hit.get(field)
                if v is not None:
                    return v
            if hasattr(hit, 'entity') and hit.entity is not None:
                return hit.entity.get(field, default)
            return default

        formatted_results = []
        for hits in results:
            for hit in hits:
                text_val = _get(hit, 'text') or ''
                image_paths_raw = _get(hit, 'image_paths') or '[]'
                formatted_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "chunk_id": _get(hit, 'chunk_id'),
                    "text": text_val if isinstance(text_val, str) else str(text_val),
                    "image_paths": json.loads(image_paths_raw) if isinstance(image_paths_raw, str) else (image_paths_raw or []),
                    "source_file": _get(hit, 'source_file'),
                    "chapter": _get(hit, 'chapter'),
                    "has_image": _get(hit, 'has_image'),
                    "search_type": "image"
                })

        need_text_ids = [r["id"] for r in formatted_results if not (r.get("text") or "").strip()]
        if need_text_ids:
            try:
                q = self.collection.query(
                    expr=f"id in {need_text_ids}",
                    output_fields=["id", "text"]
                )
                id_to_text = {row["id"]: (row.get("text") or "") for row in q}
                for r in formatted_results:
                    if not (r.get("text") or "").strip() and r["id"] in id_to_text:
                        r["text"] = id_to_text[r["id"]] or ""
            except Exception as e:
                print(f"⚠️ Не удалось догрузить текст по id: {e}")

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
        """Закрытие соединения с векторной БД"""
        connections.disconnect("default")
        print("🔌 Соединение с векторной БД закрыто")


# Публичная функция для скриптов: from multimodal_rag import check_vector_db_server
check_vector_db_server = MultimodalRAG.check_vector_db_server