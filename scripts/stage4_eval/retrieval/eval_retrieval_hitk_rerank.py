# -*- coding: utf-8 -*-
"""
Этап 4, опыт 2: Hit@1 / Hit@3 / Hit@5 по коллекции diplom_multimodal_e5_rerank.

Тот же реестр, что у опытов 0 и 1. Префикс запроса «query: », реранкер top-20 → 5.
Результат — scripts/stage4_eval/results/retrieval/stage4_hitk_results_rerank.json.
JSON опытов 0 и 1 не перезаписываются.

Запуск из корня проекта:
  python scripts/stage4_eval/retrieval/eval_retrieval_hitk_rerank.py
  powershell -File scripts/stage4_eval/run_hitk_rerank.ps1
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _bootstrap import setup_paths  # noqa: E402

ROOT = setup_paths(embed=True)
RERANK_DIR = ROOT / "src" / "preprocessing" / "Create_embeddings" / "Rerank"
sys.path.insert(0, str(RERANK_DIR))

from report_paths import STAGE4_HITK_RESULTS_RERANK, STAGE4_QUESTIONS  # noqa: E402
from rerank_rag import open_text_rag  # noqa: E402
from eval_questions_io import load_eval_questions  # noqa: E402

QUESTIONS_PATH = STAGE4_QUESTIONS
RESULTS_JSON = STAGE4_HITK_RESULTS_RERANK


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


def hit_at_k(results: list[dict], expected_clause: str, k: int) -> bool:
    return any(clause_in_text(expected_clause, hit.get("text") or "") for hit in results[:k])


def main() -> None:
    if not QUESTIONS_PATH.is_file():
        raise SystemExit(f"Нет файла вопросов: {QUESTIONS_PATH}")

    from stage4_console import log_run_start, opening_stage_banner, progress_line  # noqa: E402

    log_run_start(
        "eval_retrieval_hitk_rerank.py",
        questions_file=str(QUESTIONS_PATH.name),
        results_json=str(RESULTS_JSON.name),
    )
    questions = load_eval_questions(QUESTIONS_PATH)
    opening_stage_banner(
        "Оценка retrieval Hit@1 / Hit@3 / Hit@5 (опыт 2, реранкер)",
        detail=(
            f"{len(questions)} вопросов, коллекция diplom_multimodal_e5_rerank, "
            "префикс query:, ANN top-20 → BAAI/bge-reranker-v2-m3 → top-5"
        ),
    )
    rag, _cfg = open_text_rag()
    collection = rag.collection_name
    text_model = rag._text_model_name
    n = len(questions)
    print(
        f" Hit@k rerank: {n} вопросов, коллекция {collection}, "
        f"модель {text_model}, query: + реранкер {rag.rerank_model_name}"
    )

    k_values = (1, 3, 5)
    search_limit = 5
    hits = {k: 0 for k in k_values}
    details = []

    for i, item in enumerate(questions, start=1):
        q = item["query"]
        expected = item["expected_clause"]
        t0 = time.perf_counter()
        results = rag.search_text(q, limit=search_limit)
        duration_sec = round(time.perf_counter() - t0, 3)
        row = {
            "id": item.get("id"),
            "query": q,
            "expected_clause": expected,
            "top1_score": results[0]["score"] if results else None,
            "duration_sec": duration_sec,
            "hit": {},
        }
        for k in k_values:
            ok = hit_at_k(results, expected, k)
            if ok:
                hits[k] += 1
            row["hit"][f"@{k}"] = ok
        details.append(row)
        progress_line(
            f"  [{i}/{n}] id={item.get('id')}: "
            f"hit@1={row['hit']['@1']} hit@3={row['hit']['@3']} hit@5={row['hit']['@5']} "
            f"t={duration_sec:.2f}s | {expected}"
        )

    metrics = {f"hit@{k}": round(100.0 * hits[k] / n, 1) for k in k_values}
    num_entities = rag.collection.num_entities if rag.collection else None
    out = {
        "n_questions": n,
        "collection": collection,
        "collection_num_entities": num_entities,
        "text_model": text_model,
        "embedding_device": getattr(rag, "text_device", None),
        "e5_prefixes": {"passage": True, "query": True},
        "rerank": {
            "model": rag.rerank_model_name,
            "candidates": rag.rerank_candidates,
            "output_k": search_limit,
            "device": rag.rerank_device,
        },
        "evaluated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "source": "scripts/stage4_eval/retrieval/eval_retrieval_hitk_rerank.py",
        "questions": str(QUESTIONS_PATH),
        "metrics_percent": metrics,
        "details": details,
    }
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    rag.close()

    print(f"Вопросов: {n}, модель: {text_model}, коллекция: {collection}")
    for k in k_values:
        print(f"  Hit@{k}: {hits[k]}/{n} ({metrics[f'hit@{k}']}%)")
    print(f"Результаты: {RESULTS_JSON}")


if __name__ == "__main__":
    main()
