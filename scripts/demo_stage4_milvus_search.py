"""Демо одного search_text к Milvus для отчёта этапа 4 (ноутбук Readme-4)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBED_DIR = ROOT / "src" / "preprocessing" / "Create_embeddings"
if str(EMBED_DIR) not in sys.path:
    sys.path.insert(0, str(EMBED_DIR))

print("demo_stage4_milvus_search: старт", flush=True)
print(
    "Загрузка torch / sentence-transformers — при первом запуске 1–3 мин без вывода, это нормально",
    flush=True,
)

from multimodal_rag import MultimodalRAG, check_vector_db_server, get_default_embedding_model
from model_selector import select_text_model
from runtime_config import load_runtime_config, resolve_repo_path


def main() -> int:
    cfg = load_runtime_config(ROOT / "config" / "rag_runtime.json")
    vdb = cfg["vector_db"]
    host = vdb["host"]
    port = str(vdb["port"])
    coll = vdb["collection_name"]
    models = cfg["models"]
    qcfg = cfg["query_test"]
    base_data_path = str(resolve_repo_path(cfg["paths"]["base_data_path"]))

    if not check_vector_db_server(host, port):
        print(
            f"Milvus недоступен ({host}:{port}). "
            "Запустите: python scripts/start_report_docker.py",
            file=sys.stderr,
        )
        return 1

    meta = MultimodalRAG.get_embedding_meta_from_collection(host, port, coll)
    if meta:
        text_model = meta["text_model"]
        text_dim = meta.get("text_dim")
        print(f"Модель из коллекции: {text_model}, dim={text_dim}", flush=True)
    else:
        auto, reason = select_text_model(cfg)
        if auto:
            text_model = auto
            text_dim = None
            print(f"Модель (автовыбор): {text_model} — {reason}", flush=True)
        else:
            text_model, text_dim = get_default_embedding_model()
            print(f"Модель по умолчанию: {text_model}", flush=True)

    raw_q = str(qcfg.get("search_text", "")).lstrip("# ").strip()
    query = raw_q or "Нулевой защитный проводник"
    limit = int(qcfg.get("limit", 3))

    print(f"Загрузка embedding-модели и коллекции {coll}...", flush=True)
    rag = MultimodalRAG(
        vector_db_host=host,
        vector_db_port=port,
        collection_name=coll,
        text_model_name=text_model,
        text_dim=text_dim,
        base_data_path=base_data_path,
        device_text=models["device_text"],
        device_clip=models["device_clip"],
        load_image_model=False,
    )
    rag.load_collection()
    hits = rag.search_text(query, limit=limit)
    rag.close()

    print(f"\nЗапрос: {query}\n")
    for i, h in enumerate(hits, 1):
        score = h.get("score")
        score_s = f"{score:.3f}" if score is not None else "—"
        t = (h.get("text") or "")[:220].replace("\n", " ")
        suffix = "…" if len(h.get("text") or "") > 220 else ""
        print(f"[{i}] score={score_s}  глава={h.get('chapter')}")
        print(f"    {t}{suffix}\n")

    if not hits:
        print("(результатов нет — проверьте load_data.py и коллекцию)")
        return 1

    top = hits[0]
    top_score = top.get("score")
    top_score_s = f"{top_score:.3f}" if top_score is not None else "—"
    chapters = [str(h.get("chapter") or "—") for h in hits]
    unique_ch = sorted({c for c in chapters if c != "—"})
    ch_preview = ", ".join(unique_ch[:5])
    if len(unique_ch) > 5:
        ch_preview += f", … (+{len(unique_ch) - 5})"

    print("—" * 60)
    print("Итог демо search_text (§6 ноутбука)")
    print(f"  Коллекция Milvus : {coll}")
    print(f"  Модель эмбеддингов: {text_model}")
    print(f"  Запрос           : {query}")
    print(f"  Выдано фрагментов: {len(hits)} (limit={limit})")
    print(
        f"  Лучший результат : score={top_score_s}, "
        f"глава={top.get('chapter')}, chunk_id={top.get('chunk_id')}"
    )
    if ch_preview:
        print(f"  Главы в top-{len(hits)}  : {ch_preview}")
    print("  Режим            : только retrieval (Milvus + SentenceTransformer), LLM не вызывался.")
    print("—" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
