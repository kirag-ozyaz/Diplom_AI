# -*- coding: utf-8 -*-
"""
Скрипт мультипроцессорной загрузки данных в Multimodal RAG.
Использует multiprocessing для векторизации изображений (CLIP на CPU в отдельных процессах),
текст по-прежнему кодируется на GPU в главном процессе.

На Windows обязательно запускать через: python load_data_multiprocessing.py
(используется защита if __name__ == "__main__").
"""

from pathlib import Path
from typing import List, Optional
import json
import time
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

    def _encode_images_parallel(
        self,
        image_paths: List[str],
        pool: Optional[mp.Pool] = None,
    ) -> List[List[float]]:
        """
        Параллельная векторизация списка изображений.
        Использует imap (порядок сохраняется) для раздачи векторов по чанкам.
        pool: если передан — переиспользуется (не закрывается); иначе создаётся свой.
        """
        if not image_paths:
            return []

        model_name = getattr(self, "_clip_model_name", "ViT-B-32")
        device = getattr(self, "_device_clip", "cpu")
        tasks = [(path, model_name, device) for path in image_paths]

        def run(p):
            return list(
                tqdm(
                    p.imap(_process_image_worker, tasks),
                    total=len(tasks),
                    desc="   Обработка изображений (mp)",
                    leave=False,
                )
            )

        if pool is not None:
            return run(pool)
        with mp.Pool(processes=self.num_workers) as p:
            return run(p)

    def _encode_images_batch(self, image_paths: List[str]) -> List[float]:
        """
        Переопределение: векторизация изображений через multiprocessing,
        затем усреднение по чанку (вызывается только при отсутствии общего pool).
        """
        if not image_paths:
            return [0.0] * self.image_dim
        vectors = self._encode_images_parallel(image_paths)
        return np.mean(vectors, axis=0).tolist()

    def load_from_jsonl_folder(
        self,
        jsonl_folder: str,
        batch_size: int = 32,
        skip_existing: bool = False,
        log_every_batches: int = 3,
        log_file_summary: bool = True,
    ):
        """
        Загрузка с одним пулом процессов на весь запуск и одним вызовом
        кодирования изображений на батч (вместо одного пула на каждый чанк).
        """
        jsonl_path = Path(jsonl_folder)
        jsonl_files = list(jsonl_path.glob("*.jsonl"))
        if not jsonl_files:
            raise FileNotFoundError(f"Не найдено JSONL файлов в {jsonl_folder}")

        print(f"📂 Найдено файлов: {len(jsonl_files)}")
        total_chunks = 0
        total_images = 0

        pool = mp.Pool(processes=self.num_workers)
        try:
            for jsonl_file in jsonl_files:
                file_t0 = time.time()
                print(f"\n📄 Обработка файла: {jsonl_file.name}")

                if jsonl_file.name.endswith(".chunked.jsonl"):
                    chapter = jsonl_file.name[: -len(".chunked.jsonl")]
                else:
                    chapter = jsonl_file.stem

                chunks = []
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            chunks.append(json.loads(line))

                print(f"   Найдено чанков: {len(chunks)}")
                if log_file_summary:
                    num_batches = (len(chunks) + batch_size - 1) // batch_size if chunks else 0
                    print(f"   Глава: {chapter} | Батчей: {num_batches} | batch_size: {batch_size}")

                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    texts = [(chunk.get("text") or chunk.get("content") or "") for chunk in batch]
                    text_vectors = self._encode_text(texts)

                    image_paths_list = []
                    has_images = []
                    chunk_image_paths = []
                    for chunk in batch:
                        img_paths = self._extract_images_from_chunk(
                            chunk.get("text") or chunk.get("content") or "",
                            chapter,
                            base_dir=jsonl_file.parent,
                        )
                        meta_images = (
                            chunk.get("metadata", {}).get("image_paths", [])
                            or chunk.get("image_paths", [])
                        )
                        if meta_images:
                            for img_name in meta_images:
                                meta_found = self._extract_images_from_chunk(
                                    str(img_name), chapter, base_dir=jsonl_file.parent
                                )
                                img_paths.extend(meta_found)
                        img_paths = list(set(img_paths))
                        chunk_image_paths.append(img_paths)
                        image_paths_list.append(json.dumps(img_paths, ensure_ascii=False))
                        has_images.append(len(img_paths) > 0)

                    batch_images = sum(len(p) for p in chunk_image_paths)
                    total_images += batch_images

                    # Один вызов пула на весь батч: все пути подряд → раздача по чанкам
                    all_paths = [p for paths in chunk_image_paths for p in paths]
                    if all_paths:
                        all_vectors = self._encode_images_parallel(all_paths, pool=pool)
                        vec_idx = 0
                        image_vectors = []
                        for paths in chunk_image_paths:
                            if paths:
                                n = len(paths)
                                chunk_vecs = all_vectors[vec_idx : vec_idx + n]
                                image_vectors.append(np.mean(chunk_vecs, axis=0).tolist())
                                vec_idx += n
                            else:
                                image_vectors.append([0.0] * self.image_dim)
                    else:
                        image_vectors = [[0.0] * self.image_dim for _ in chunk_image_paths]

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
                    self.collection.insert(entities)
                    total_chunks += len(batch)

                    if log_every_batches and ((i // batch_size) % log_every_batches == 0):
                        batch_no = (i // batch_size) + 1
                        total_batches = (len(chunks) + batch_size - 1) // batch_size
                        print(
                            f"   [{jsonl_file.name}] батч {batch_no}/{total_batches}: "
                            f"вставлено {len(batch)} | 🖼️ в батче {batch_images} | "
                            f"прогресс {min(i + batch_size, len(chunks))}/{len(chunks)}"
                        )

                self.collection.flush()
                if log_file_summary:
                    dt = time.time() - file_t0
                    try:
                        ents = self.collection.num_entities
                    except Exception:
                        ents = "?"
                    print(
                        f"✅ Файл завершён: {jsonl_file.name} | time={dt:.1f}s | сущностей в коллекции={ents}"
                    )

            print(f"\n✅ Загрузка завершена!")
            print(f"   📊 Всего чанков: {total_chunks}")
            print(f"   🖼️ Всего изображений: {total_images}")
            print(f"   📦 Сущностей в коллекции: {self.collection.num_entities}")
        finally:
            pool.close()
            pool.join()


def main():
    print("🚀 Запуск мультипроцессорной загрузки данных в Multimodal RAG...")
    ROOT = Path(__file__).resolve().parent.parent.parent.parent
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
