# -*- coding: utf-8 -*-
"""
Скрипт мультипроцессорной загрузки данных в Multimodal RAG.
Использует multiprocessing для векторизации изображений (CLIP на CPU в отдельных процессах),
текст по-прежнему кодируется на GPU в главном процессе.

На Windows обязательно запускать через: python load_data_multiprocessing.py
(используется защита if __name__ == "__main__").
"""

from pathlib import Path
import sys

# Чтобы импорт multimodal_rag работал при запуске из папки trash/ или из корня проекта
_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from typing import List
import multiprocessing as mp

import numpy as np
import torch
from PIL import Image
import open_clip
from tqdm import tqdm

from multimodal_rag import MultimodalRAG


# --- Воркер для multiprocessing: должен быть на уровне модуля (picklable на Windows) ---
def _process_image_worker(args):
    """
    Обработка одного изображения в отдельном процессе.
    Каждый процесс загружает свою копию CLIP (на CPU), чтобы обойти GIL.
    """
    img_path, model_name, device = args
    image_dim = 512
    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained="laion2b_e16"
        )
        model = model.to(device)
        model.eval()

        image = Image.open(img_path).convert("RGB")
        image_input = preprocess(image).unsqueeze(0).to(device)

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        vec = image_features.cpu().numpy()[0].tolist()

        del model
        if device == "cuda":
            torch.cuda.empty_cache()

        return vec
    except Exception as e:
        print(f"⚠️ Ошибка обработки {img_path}: {e}")
        return [0.0] * image_dim


class MultimodalRAGMultiprocessing(MultimodalRAG):
    """
    Multimodal RAG с мультипроцессорной векторизацией изображений.
    Текст кодируется на GPU в главном процессе, изображения — в пуле процессов (CLIP на CPU).
    """

    def __init__(
        self,
        num_workers: int = 4,
        **kwargs,
    ):
        # Отключаем потоковую параллелизацию изображений в базовом классе
        kwargs.setdefault("image_encode_workers", 0)
        kwargs.setdefault("batch_chunk_workers", 0)
        super().__init__(**kwargs)
        self.num_workers = max(1, num_workers)
        print(f"   🔀 Процессов для изображений (multiprocessing): {self.num_workers}")

    def _encode_images_parallel(self, image_paths: List[str]) -> List[List[float]]:
        """Параллельная векторизация списка изображений через пул процессов."""
        if not image_paths:
            return []

        model_name = getattr(self, "_clip_model_name", "ViT-B-32")
        device = getattr(self, "_device_clip", "cpu")
        tasks = [(path, model_name, device) for path in image_paths]

        vectors = []
        with mp.Pool(processes=self.num_workers) as pool:
            for vec in tqdm(
                pool.imap_unordered(_process_image_worker, tasks),
                total=len(tasks),
                desc="   Обработка изображений (mp)",
                leave=False,
            ):
                vectors.append(vec)
        return vectors

    def _encode_images_batch(self, image_paths: List[str]) -> List[float]:
        """
        Переопределение: векторизация изображений через multiprocessing,
        затем усреднение по чанку (как в базовом классе).
        """
        if not image_paths:
            return [0.0] * self.image_dim
        vectors = self._encode_images_parallel(image_paths)
        return np.mean(vectors, axis=0).tolist()


def main():
    print("🚀 Запуск мультипроцессорной загрузки данных в Multimodal RAG...")
    # Скрипт в trash/ — на уровень глубже, чем load_data.py; нужен корень проекта (5 родителей)
    ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
    chunked_root = ROOT / "data" / "chunked"

    rag = MultimodalRAGMultiprocessing(
        milvus_host="localhost",
        milvus_port="19530",
        collection_name="diplom_multimodal_1",
        text_model_name="BAAI/bge-small-en-v1.5",
        clip_model_name="ViT-B-32",
        device_text="cuda",
        device_clip="cpu",
        base_data_path=str(chunked_root),
        num_workers=4,
    )

    rag.create_collection(drop_existing=True)

    rag.load_from_jsonl_folder(
        jsonl_folder=str(chunked_root),
        batch_size=32,
        skip_existing=False,
        log_every_batches=1,
        log_file_summary=True,
    )

    rag.load_collection()

    stats = rag.get_collection_stats()
    print(f"\n📊 Статистика коллекции:")
    print(f"   Название: {stats['name']}")
    print(f"   Сущностей: {stats['num_entities']}")
    print(f"   Поля: {stats['schema']}")

    rag.close()
    print("\n✅ Мультипроцессорная загрузка завершена успешно!")


if __name__ == "__main__":
    main()
