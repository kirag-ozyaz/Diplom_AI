# -*- coding: utf-8 -*-
"""
Этап 4: оценка Hit@1 / Hit@3 / Hit@5 для семантического поиска по ПУЭ.
Запуск из корня: python scripts/eval_retrieval_hitk.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBED_DIR = ROOT / "src" / "preprocessing" / "Create_embeddings"
REPORTS = ROOT / "Этапы" / "Reports"
QUESTIONS_PATH = REPORTS / "stage4_eval_questions.json"
RESULTS_JSON = REPORTS / "stage4_hitk_results.json"
CHART_PATH = REPORTS / "stage4_hitk_chart.png"
REPORT_CHART_PATH = REPORTS / "stage4_hitk_report.png"

sys.path.insert(0, str(EMBED_DIR))

from runtime_config import load_runtime_config  # noqa: E402
from model_selector import select_text_model  # noqa: E402
from multimodal_rag import (  # noqa: E402
    MultimodalRAG,
    check_vector_db_server,
    get_default_embedding_model,
)


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
    for hit in results[:k]:
        if clause_in_text(expected_clause, hit.get("text") or ""):
            return True
    return False


def run_hitk_eval(*, refresh_readme: bool = True) -> dict:
    """Прогон Hit@k по Milvus; пишет JSON/PNG. Для ноутбука и CLI."""
    cfg = load_runtime_config()
    vdb = cfg["vector_db"]
    host = vdb["host"]
    port = str(vdb["port"])
    collection = vdb["collection_name"]

    if not check_vector_db_server(host, port):
        raise RuntimeError(
            "Milvus недоступен. Запустите: python scripts/start_milvus.py "
            "или docker-ячейку ноутбука (§5.1)."
        )

    if not QUESTIONS_PATH.is_file():
        raise RuntimeError(f"Нет файла вопросов: {QUESTIONS_PATH}")

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    meta = MultimodalRAG.get_embedding_meta_from_collection(host, port, collection)
    if meta:
        text_model = meta["text_model"]
        text_dim = meta.get("text_dim")
    else:
        text_model, _ = select_text_model(cfg)
        text_model, text_dim = get_default_embedding_model()

    models_cfg = cfg["models"]
    rag = MultimodalRAG(
        vector_db_host=host,
        vector_db_port=port,
        collection_name=collection,
        text_model_name=text_model,
        text_dim=text_dim,
        device_text=models_cfg["device_text"],
        device_clip=models_cfg["device_clip"],
        load_image_model=False,
    )
    rag.load_collection()
    num_entities = rag.collection.num_entities if rag.collection else None
    embedding_device = getattr(rag, "text_device", None)

    k_values = (1, 3, 5)
    search_limit = 5
    hits = {k: 0 for k in k_values}
    details = []

    for item in questions:
        q = item["query"]
        expected = item["expected_clause"]
        results = rag.search_text(q, limit=search_limit)
        row = {
            "id": item.get("id"),
            "query": q,
            "expected_clause": expected,
            "top1_score": results[0]["score"] if results else None,
            "hit": {},
        }
        for k in k_values:
            ok = hit_at_k(results, expected, k)
            if ok:
                hits[k] += 1
            row["hit"][f"@{k}"] = ok
        details.append(row)

    n = len(questions)
    metrics = {f"hit@{k}": round(100.0 * hits[k] / n, 1) for k in k_values}

    out = {
        "n_questions": n,
        "collection": collection,
        "collection_num_entities": num_entities,
        "text_model": text_model,
        "embedding_device": embedding_device,
        "evaluated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "source": "eval_retrieval_hitk.py",
        "metrics_percent": metrics,
        "details": details,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.path.insert(0, str(ROOT / "scripts"))
    from stage4_hitk_report import append_run_history  # noqa: E402

    append_run_history(out)

    print(f"Вопросов: {n}, модель: {text_model}")
    for k in k_values:
        print(f"  Hit@{k}: {hits[k]}/{n} ({metrics[f'hit@{k}']}%)")
    print(f"Результаты: {RESULTS_JSON}")

    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from plot_stage4_hitk import plot_hitk_bar_chart, plot_hitk_report  # noqa: E402

        plot_hitk_bar_chart(out, CHART_PATH)
        print(f"PNG 1 (Word/md): {CHART_PATH}")
        plot_hitk_report(out, REPORT_CHART_PATH)
        print(f"PNG 2 (Word/md): {REPORT_CHART_PATH}")
    except ImportError:
        print("matplotlib не установлен — график не сохранён (pip install matplotlib)")

    if refresh_readme:
        try:
            from update_readme4_eval_docs import refresh_readme4_eval_docs  # noqa: E402

            refresh_readme4_eval_docs(sync_notebook=True)
        except Exception as exc:
            print(f"Readme-4.md не обновлён ({exc}). Вручную: python scripts/update_readme4_eval_docs.py")

    rag.close()
    return out


def main() -> None:
    try:
        run_hitk_eval()
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
