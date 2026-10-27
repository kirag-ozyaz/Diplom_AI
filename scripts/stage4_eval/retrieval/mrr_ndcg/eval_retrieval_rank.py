# -*- coding: utf-8 -*-
"""
Этап 4: ранговая оценка retrieval (MRR, MRR@k, nDCG@k, Hit@k) для трёх опытов.

Повторяет логику eval_retrieval_hitk*.py (тот же реестр вопросов, те же коллекции,
тот же rag.search_text и тот же clause_in_text), но берёт top-k_max (по умолчанию 10)
и сохраняет позицию первого релевантного результата.

  --mode base   → как eval_retrieval_hitk.py        (diplom_multimodal, MultimodalRAG)
  --mode e5     → как eval_retrieval_hitk_e5.py     (diplom_multimodal_e5, query:/passage:)
  --mode rerank → как eval_retrieval_hitk_rerank.py (diplom_multimodal_e5_rerank, ANN top-20 → bge-reranker-v2-m3)

Запуск из корня проекта:
  python scripts/stage4_eval/retrieval/mrr_ndcg/eval_retrieval_rank.py --mode base
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE4 = HERE.parent.parent
sys.path.insert(0, str(HERE))
from rank_metrics import (  # noqa: E402
    DEFAULT_KS,
    refresh_rank_comparison,
    summarize_ranks,
    summarize_rel_lists,
)

DEFAULT_RESULTS_DIR = STAGE4 / "results" / "retrieval"
OUT_NAMES = {"base": "stage4_rank_results_base.json",
             "e5": "stage4_rank_results_e5.json",
             "rerank": "stage4_rank_results_rerank.json"}


# --- копия из eval_retrieval_hitk*.py (без изменений) ---
def clause_in_text(clause: str, text: str) -> bool:
    if not clause or not text:
        return False
    escaped = re.escape(clause)
    patterns = [
        rf"\b{escaped}\b",
        rf"Пункт\s+{escaped}",
        rf"п\.\s*{escaped}",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def as_clause_list(expected) -> list[str]:
    if expected is None:
        return []
    if isinstance(expected, (list, tuple)):
        return [str(x) for x in expected if x]
    return [str(expected)]


def rank_info(results: list[dict], expected, dedup: bool = False) -> dict:
    """
    rank — позиция (1-based) первого результата, содержащего любой из expected_clause.
    По умолчанию позиция = позиция чанка (как в hit_at_k оригинала, без дедупликации).
    dedup=True: каждый ожидаемый пункт засчитывается только один раз (повторные чанки
    того же пункта → релевантность 0) — нужно для nDCG при нескольких пунктах.
    """
    clauses = as_clause_list(expected)
    rels, matched, seen = [], [], set()
    for hit in results:
        text = hit.get("text") or ""
        found = [c for c in clauses if clause_in_text(c, text)]
        new = [c for c in found if c not in seen] if dedup else found
        seen.update(found)
        rels.append(1 if new else 0)
        matched.append(found)
    rank = next((i + 1 for i, r in enumerate(rels) if r), None)
    return {"rank": rank, "rels": rels, "n_relevant": len(clauses), "matched": matched}


def open_rag(mode: str):
    """Открывает RAG так же, как соответствующий оригинальный скрипт."""
    sys.path.insert(0, str(STAGE4 / "lib"))
    from _bootstrap import setup_paths  # noqa: E402

    root = setup_paths(embed=True)
    embed_dir = root / "src" / "preprocessing" / "Create_embeddings"
    if mode == "e5":
        sys.path.insert(0, str(embed_dir / "E5"))
        from e5_rag import open_text_rag  # noqa: E402
        rag, _ = open_text_rag()
        return rag, {"e5_prefixes": {"passage": True, "query": True}}
    if mode == "rerank":
        sys.path.insert(0, str(embed_dir / "Rerank"))
        from rerank_rag import open_text_rag  # noqa: E402
        rag, _ = open_text_rag()
        return rag, {"e5_prefixes": {"passage": True, "query": True},
                     "rerank": {"model": rag.rerank_model_name, "candidates": rag.rerank_candidates,
                                "device": rag.rerank_device}}
    # base — как run_hitk_eval()
    sys.path.insert(0, str(embed_dir))
    from runtime_config import load_runtime_config  # noqa: E402
    from model_selector import select_text_model  # noqa: E402
    from multimodal_rag import MultimodalRAG, check_vector_db_server, get_default_embedding_model  # noqa: E402

    cfg = load_runtime_config()
    vdb = cfg["vector_db"]
    host, port, collection = vdb["host"], str(vdb["port"]), vdb["collection_name"]
    if not check_vector_db_server(host, port):
        raise RuntimeError("Milvus недоступен. Запустите: python scripts/infra_start_system/start_milvus.py")
    meta = MultimodalRAG.get_embedding_meta_from_collection(host, port, collection)
    if meta:
        text_model, text_dim = meta["text_model"], meta.get("text_dim")
    else:
        text_model, _ = select_text_model(cfg)
        text_model, text_dim = get_default_embedding_model()
    m = cfg["models"]
    rag = MultimodalRAG(vector_db_host=host, vector_db_port=port, collection_name=collection,
                        text_model_name=text_model, text_dim=text_dim, device_text=m["device_text"],
                        device_clip=m["device_clip"], load_image_model=False)
    rag.load_collection()
    return rag, {}


def default_questions_path() -> Path:
    sys.path.insert(0, str(STAGE4 / "lib"))
    from _bootstrap import setup_paths  # noqa: E402
    setup_paths(embed=True)
    from report_paths import STAGE4_QUESTIONS  # noqa: E402
    return Path(STAGE4_QUESTIONS)


def load_questions(path: Path) -> list[dict]:
    try:
        from eval_questions_io import load_eval_questions  # noqa: E402
        return load_eval_questions(path)
    except ImportError:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["questions"] if isinstance(data, dict) else data


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Ранговая оценка retrieval: MRR / nDCG@k / Hit@k")
    ap.add_argument("--mode", choices=["base", "e5", "rerank"], required=True)
    ap.add_argument("--k-max", type=int, default=10, help="глубина выдачи (limit в search_text)")
    ap.add_argument("--ks", default="1,3,5,10", help="k для Hit@k/MRR@k/nDCG@k")
    ap.add_argument("--questions", type=Path, default=None, help="по умолчанию STAGE4_QUESTIONS из report_paths")
    ap.add_argument("--out", type=Path, default=None, help="по умолчанию results/retrieval/stage4_rank_results_<mode>.json")
    ap.add_argument("--dedup", action="store_true", help="считать каждый ожидаемый пункт один раз (см. rank_info)")
    ap.add_argument("--limit-questions", type=int, default=None, help="для отладки: первые N вопросов")
    ap.add_argument(
        "--no-refresh-readme",
        action="store_true",
        help="не обновлять Readme-4.md после полного набора rank JSON",
    )
    a = ap.parse_args(argv)
    a.ks = tuple(int(x) for x in a.ks.split(","))
    if max(a.ks) > a.k_max:
        ap.error("--k-max должен быть >= max(--ks)")
    if a.out is None:
        a.out = DEFAULT_RESULTS_DIR / OUT_NAMES[a.mode]
    return a


def main(argv=None) -> int:
    a = parse_args(argv)
    qpath = a.questions or default_questions_path()
    questions = load_questions(qpath)
    if a.limit_questions:
        questions = questions[: a.limit_questions]
    rag, extra = open_rag(a.mode)
    collection = getattr(rag, "collection_name", None)
    text_model = getattr(rag, "_text_model_name", None)
    n = len(questions)
    print(f"Rank eval [{a.mode}]: {n} вопросов, коллекция {collection}, top-{a.k_max}", flush=True)

    details, ranks, rel_lists, n_rels = [], [], [], []
    for i, item in enumerate(questions, start=1):
        q, expected = item["query"], item["expected_clause"]
        t0 = time.perf_counter()
        results = rag.search_text(q, limit=a.k_max)
        dt = round(time.perf_counter() - t0, 3)
        info = rank_info(results, expected, dedup=a.dedup)
        ranks.append(info["rank"]); rel_lists.append(info["rels"]); n_rels.append(info["n_relevant"])
        details.append({
            "id": item.get("id"), "query": q, "expected_clause": expected,
            "rank": info["rank"], "rels": info["rels"],
            "top1_score": results[0]["score"] if results else None,
            "scores": [r.get("score") for r in results], "duration_sec": dt,
        })
        print(f"  [{i}/{n}] id={item.get('id')}: rank={info['rank']} | {expected}", flush=True)

    metrics = summarize_ranks(ranks, a.ks, a.k_max)
    if any(m > 1 for m in n_rels):  # несколько пунктов → nDCG по полному вектору
        metrics.update(summarize_rel_lists(rel_lists, n_rels, a.ks))
    out = {
        "n_questions": n, "mode": a.mode, "collection": collection, "text_model": text_model,
        "embedding_device": getattr(rag, "text_device", None), **extra,
        "k_max": a.k_max, "ks": list(a.ks), "dedup": a.dedup,
        "evaluated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "source": "scripts/stage4_eval/retrieval/mrr_ndcg/eval_retrieval_rank.py",
        "questions": str(qpath), "metrics": metrics,
        "metrics_percent": {k: round(100 * v, 1) for k, v in metrics.items() if k.startswith("hit@")},
        "details": details,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        rag.close()
    except Exception:
        pass
    for k, v in metrics.items():
        if k != "n":
            print(f"  {k}: {v:.4f}")
    print(f"Результаты: {a.out}")
    _postprocess_rank_results(refresh_readme=not a.no_refresh_readme)
    return 0


def _postprocess_rank_results(*, refresh_readme: bool) -> None:
    """Сводка md/csv и (при полном наборе JSON) Readme-4 — как после Hit@k."""
    comparison = refresh_rank_comparison()
    if comparison:
        print(f"Сводка MRR/nDCG: {comparison}")
    elif refresh_readme:
        print("Сводка MRR/nDCG: ждём все три stage4_rank_results_{base,e5,rerank}.json")
    if not refresh_readme or not comparison:
        return
    try:
        sys.path.insert(0, str(STAGE4.parent / "reports"))
        from update_readme4_eval_docs import refresh_readme4_eval_docs  # noqa: E402

        refresh_readme4_eval_docs(sync_notebook=True)
        print("Readme-4.md обновлён (в т.ч. §5.4, MRR/nDCG)")
    except Exception as exc:
        print(
            f"Readme-4.md не обновлён ({exc}). "
            "Вручную: python scripts/stage4_eval/reports/update_readme4_eval_docs.py"
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
