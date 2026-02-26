Да, **потоки (threading) и процессы (multiprocessing) — это отличная альтернатива асинхронности**, особенно для вашей задачи.

Учитывая ваше железо (**64 ГБ ОЗУ** и **RTX 2060 6GB**), у вас есть ресурсы для параллелизации, но есть критически важный нюанс с видеопамятью.

### 1. Что выбрать: Потоки или Процессы?

В Python есть ограничение (GIL), которое влияет на выбор:

| Метод | Как работает | Для вашей задачи |
| :--- | :--- | :--- |
| **Threading (Потоки)** | Работают в одном процессе. GIL мешает параллельным вычислениям. | ✅ **Хорошо для I/O:** Запись в Milvus, чтение файлов, сеть. <br> ❌ **Плохо для векторизации:** Не ускорит работу модели (CPU/GPU). |
| **Multiprocessing (Процессы)** | Разные процессы, нет GIL. | ✅ **Идеально для CPU:** Векторизация изображений (CLIP на CPU). <br> ⚠️ **Опасно для GPU:** Если каждый процесс полезет в CUDA, будет ошибка `CUDA out of memory`. |

### 2. Рекомендованная стратегия (Гибридная)

Чтобы не переполнить 6 ГБ видеопамяти, но ускорить загрузку:

1.  **Текст (GPU):** Обрабатываем **последовательно** крупными батчами. Модель сама загрузит видеокарту на 100%, параллелить тут не нужно.
2.  **Изображения (CPU):** Обрабатываем через **`multiprocessing`**. Так как CLIP работает на процессоре, можно запустить 4–6 параллельных процессов для ускорения.
3.  **Запись в Milvus:** Делаем асинхронно или отдельным потоком, чтобы не блокировать обработку.

### 3. Готовое решение (Обновленный класс)

Вот оптимизированная версия метода загрузки с использованием `multiprocessing` для изображений и безопасной работой с GPU.

```python
# -*- coding: utf-8 -*-
"""
MultimodalRAG с ускоренной загрузкой (Multiprocessing для CPU)
"""

import os
import json
import glob
from typing import List, Dict, Optional
from pathlib import Path
from tqdm import tqdm
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor

import torch
from PIL import Image
from sentence_transformers import SentenceTransformer
import open_clip
import numpy as np

from pymilvus import connections, utility, FieldSchema, CollectionSchema, DataType, Collection


class MultimodalRAG:
    def __init__(
        self,
        milvus_host: str = "localhost",
        milvus_port: str = "19530",
        collection_name: str = "diplom_multimodal",
        text_model_name: str = "BAAI/bge-small-en-v1.5",
        clip_model_name: str = "ViT-B-32",
        device_text: str = "cuda",
        device_clip: str = "cpu",
        base_data_path: str = "data",
        num_workers: int = 4  # Количество процессов для CPU
    ):
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = collection_name
        self.base_data_path = Path(base_data_path)
        self.text_dim = 384
        self.image_dim = 512
        self.num_workers = num_workers
        
        self._connect_milvus()
        self._load_text_model(text_model_name, device_text)
        # CLIP загружаем только для инициализации, в процессах будут свои копии
        self._load_clip_model(clip_model_name, device_clip)
        
        print(f"✅ MultimodalRAG инициализирован (Потоков: {num_workers})")

    def _connect_milvus(self):
        connections.connect(host=self.milvus_host, port=self.milvus_port)
        print(f"✅ Подключение к Milvus: {self.milvus_host}:{self.milvus_port}")

    def _load_text_model(self, model_name: str, device: str):
        print(f"📥 Загрузка текстовой модели: {model_name}")
        self.text_model = SentenceTransformer(model_name)
        self.text_device = device
        print("✅ Текстовая модель готова")

    def _load_clip_model(self, model_name: str, device: str):
        print(f"📥 Загрузка CLIP модели: {model_name}")
        self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained='laion2b_e16'
        )
        self.clip_model = self.clip_model.to(device)
        self.clip_model.eval()
        self.clip_device = device
        print("✅ CLIP модель готова")

    def create_collection(self, drop_existing: bool = True):
        if utility.has_collection(self.collection_name):
            if drop_existing:
                print(f"⚠️ Коллекция '{self.collection_name}' существует. Удаляем...")
                utility.drop_collection(self.collection_name)
            else:
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
        schema = CollectionSchema(fields, "Multimodal коллекция для диплома ИИ")
        self.collection = Collection(self.collection_name, schema)
        
        # Индексы
        self.collection.create_index(field_name="text_vector", index_params={
            "metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 8, "efConstruction": 200}
        })
        self.collection.create_index(field_name="image_vector", index_params={
            "metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 8, "efConstruction": 200}
        })
        print("✅ Коллекция и индексы созданы")

    # --- Worker функция для multiprocessing (должна быть глобальной) ---
    @staticmethod
    def _process_image_worker(args):
        """
        Отдельная функция для обработки изображения в процессе.
        Каждый процесс загрузит свою копию модели.
        """
        img_path, model_name, device = args
        try:
            # Загружаем модель внутри процесса (изолированно)
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name, pretrained='laion2b_e16'
            )
            model = model.to(device)
            model.eval()
            
            image = Image.open(img_path).convert('RGB')
            image_input = preprocess(image).unsqueeze(0).to(device)
            
            with torch.no_grad():
                image_features = model.encode_image(image_input)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            vec = image_features.cpu().numpy()[0].tolist()
            
            # Освобождаем память процесса
            del model
            if device == 'cuda':
                torch.cuda.empty_cache()
                
            return vec
        except Exception as e:
            print(f"⚠️ Ошибка обработки {img_path}: {e}")
            return [0.0] * 512

    def _encode_text(self, texts: List[str]) -> List[List[float]]:
        """Векторизация текста (GPU, последовательно)"""
        embeddings = self.text_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def _encode_images_parallel(self, image_paths: List[str]) -> List[List[float]]:
        """
        Параллельная векторизация изображений (CPU/Multiprocessing).
        """
        if not image_paths:
            return []
        
        # Подготовка задач
        tasks = [(path, 'ViT-B-32', self.clip_device) for path in image_paths]
        
        vectors = []
        # Запуск пула процессов
        with mp.Pool(processes=self.num_workers) as pool:
            # imap_unordered дает результаты по мере готовности (быстрее)
            for vec in tqdm(pool.imap_unordered(MultimodalRAG._process_image_worker, tasks), 
                           total=len(tasks), desc="   Обработка изображений"):
                vectors.append(vec)
        
        return vectors

    def load_from_jsonl_folder(self, jsonl_folder: str, batch_size: int = 32):
        jsonl_path = Path(jsonl_folder)
        jsonl_files = list(jsonl_path.glob("*.jsonl"))
        
        if not jsonl_files:
            raise FileNotFoundError(f"Не найдено JSONL файлов в {jsonl_folder}")
        
        print(f"📂 Найдено файлов: {len(jsonl_files)}")
        total_chunks = 0
        total_images = 0
        
        for jsonl_file in jsonl_files:
            print(f"\n📄 Обработка файла: {jsonl_file.name}")
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
                texts = [chunk.get('text', '') for chunk in batch]
                
                # 1. Текст (GPU, последовательно)
                text_vectors = self._encode_text(texts)
                
                # 2. Изображения (CPU, параллельно)
                all_image_paths = []
                chunk_image_paths = []
                
                import re
                for chunk in batch:
                    img_paths = []
                    # Поиск имен файлов в тексте
                    matches = re.findall(r'(img_[a-zA-Z0-9_]+\.(?:png|jpg|jpeg))', chunk.get('text', ''))
                    image_folder = self.base_data_path / f"image_{chapter}"
                    
                    for img_name in matches:
                        img_path = image_folder / img_name
                        if img_path.exists():
                            img_paths.append(str(img_path))
                    
                    # Из метаданных
                    meta_images = chunk.get('metadata', {}).get('image_paths', [])
                    for img_name in meta_images:
                        img_path = image_folder / img_name
                        if img_path.exists() and str(img_path) not in img_paths:
                            img_paths.append(str(img_path))
                    
                    chunk_image_paths.append(img_paths)
                    all_image_paths.extend(img_paths)
                
                # Запускаем параллельную обработку всех картинок батча
                if all_image_paths:
                    all_vectors = self._encode_images_parallel(all_image_paths)
                else:
                    all_vectors = []
                
                # Распределяем векторы обратно по чанкам (усреднение если картинок > 1)
                image_vectors = []
                vec_idx = 0
                for paths in chunk_image_paths:
                    if len(paths) > 0:
                        # Берем векторы для текущих путей
                        chunk_vecs = all_vectors[vec_idx:vec_idx+len(paths)]
                        # Усредняем
                        avg_vec = np.mean(chunk_vecs, axis=0).tolist()
                        image_vectors.append(avg_vec)
                        vec_idx += len(paths)
                        total_images += len(paths)
                    else:
                        image_vectors.append([0.0] * self.image_dim)
                
                # Формирование сущностей
                entities = [
                    [chunk.get('id', f"{chapter}_{j}") for j, chunk in enumerate(batch)],
                    text_vectors,
                    image_vectors,
                    [chunk.get('text', '') for chunk in batch],
                    [json.dumps(paths, ensure_ascii=False) for paths in chunk_image_paths],
                    [str(jsonl_file.name) for _ in batch],
                    [chapter for _ in batch],
                    [len(paths) > 0 for paths in chunk_image_paths]
                ]
                
                self.collection.insert(entities)
                total_chunks += len(batch)
                
                if (i // batch_size) % 3 == 0:
                    print(f"   Загружено: {min(i + batch_size, len(chunks))} / {len(chunks)}")
            
            self.collection.flush()
        
        print(f"\n✅ Загрузка завершена!")
        print(f"   📊 Всего чанков: {total_chunks}")
        print(f"   🖼️ Всего изображений: {total_images}")

    def load_collection(self):
        if not hasattr(self, 'collection'):
            self.collection = Collection(self.collection_name)
        self.collection.load()
        print("✅ Коллекция загружена в память")

    def close(self):
        connections.disconnect("default")
        print("🔌 Соединение с Milvus закрыто")
```

### 4. Как это использовать

```python
from multimodal_rag import MultimodalRAG

rag = MultimodalRAG(
    milvus_host="localhost",
    milvus_port="19530",
    num_workers=4  # 4 процесса для обработки изображений
)

rag.create_collection(drop_existing=True)
rag.load_from_jsonl_folder(jsonl_folder="data/chunked", batch_size=32)
rag.load_collection()
rag.close()
```

### 5. Важные предупреждения

1.  **Защита `if __name__ == "__main__":`**:
    При использовании `multiprocessing` на Windows **обязательно** оборачивайте запуск скрипта в эту конструкцию, иначе процессы начнут клонироваться бесконечно.
    ```python
    if __name__ == "__main__":
        # Запуск загрузки
    ```
2.  **Оперативная память**:
    Каждый процесс копирует модель CLIP. При 64 ГБ ОЗУ вы можете позволить себе 4–6 процессов. Если начнутся тормоза — уменьшите `num_workers`.
3.  **Видеопамять**:
    В коде выше для воркеров указан `device='cpu'`. Это критически важно. Если поставите `cuda`, 6 ГБ видеопамяти переполнятся мгновенно при 4 процессах.
4.  **Threading для записи**:
    Если хотите ускорить именно запись в Milvus, можно использовать `ThreadPoolExecutor` для вызова `collection.insert()`, но обычно база данных сама справляется с очередью, и узким местом остается векторизация.

### Итог
**Да, используйте `multiprocessing` для изображений (CPU)** и **последовательные батчи для текста (GPU)**. Это даст максимальную скорость на вашем железе без риска ошибок памяти.