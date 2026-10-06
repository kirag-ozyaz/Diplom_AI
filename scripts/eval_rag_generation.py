# -*- coding: utf-8 -*-
"""
Этап 4+: оценка generation / citation / groundedness на том же наборе
вопросов, что и Hit@k (Этапы/Reports/stage4_eval_questions.json).

Режимы:
  live   — Milvus + Ollama через src.rag.rag_service.answer
  mock   — офлайн: контекст из data/chunked/*.jsonl (и опционально hit@k JSON)
  dry-run — то же, что mock (алиас)

Запуск из корня репозитория:
  python scripts/eval_rag_generation.py
  python scripts/eval_rag_generation.py --mode live
  python scripts/eval_rag_generation.py --mode mock --limit 5
  python scripts/eval_rag_generation.py --out /workspace/stage4_gen_eval_results.json

Инфра:
  python scripts/start_milvus.py
  python scripts/start_ollama.py --pull
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "Этапы" / "Reports"
QUESTIONS_PATH = REPORTS / "stage4_eval_questions.json"
HITK_JSON = REPORTS / "stage4_hitk_results.json"
CHUNKED_DIR = ROOT / "data" / "chunked"
DEFAULT_OUT = ROOT / "Этапы" / "Reports" / "stage4_gen_eval_results.json"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src" / "preprocessing" / "Create_embeddings"))


def clause_in_text(clause: str, text: str) -> bool:
    """Те же эвристики, что в eval_retrieval_hitk.py."""
    if not clause or not text:
        return False
    escaped = re.escape(clause)
    patterns = [
        rf"\b{escaped}\b",
        rf"Пункт\s+{escaped}",
        rf"п\.\s*{escaped}",
        rf"п\s+{escaped}",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9\.]+", (text or "").lower())


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def groundedness_score(answer: str, contexts: list[str]) -> dict[str, Any]:
    """
    Эвристика: доля содержательных предложений ответа, у которых
    ≥30% токенов (длиной >2) встречаются в объединённом контексте.
    Пустой ответ / отказ без опоры на контекст → 0.
    """
    ctx = " ".join(contexts or [])
    ctx_toks = set(t for t in tokenize(ctx) if len(t) > 2)
    sents = sentence_split(answer)
    if not sents:
        return {"score": 0.0, "supported": 0, "total": 0, "method": "token_overlap"}

    refusal = re.search(
        r"нет (?:в |однозначного ответа)|не\s+найдено|не могу ответить|недостаточно (данных|контекста)|контексте нет",
        answer,
        re.I,
    )
    # Честный отказ при слабом/чужом контексте считаем grounded
    if refusal:
        return {"score": 1.0, "supported": 1, "total": 1, "method": "refusal_ok"}

    supported = 0
    details = []
    for s in sents:
        toks = [t for t in tokenize(s) if len(t) > 2]
        if len(toks) < 3:
            details.append({"sentence": s[:120], "supported": None, "overlap": 0.0})
            continue
        if not ctx_toks:
            details.append({"sentence": s[:120], "supported": False, "overlap": 0.0})
            continue
        ov = sum(1 for t in toks if t in ctx_toks) / len(toks)
        ok = ov >= 0.30
        if ok:
            supported += 1
        details.append({"sentence": s[:120], "supported": ok, "overlap": round(ov, 3)})

    scored = [d for d in details if d["supported"] is not None]
    total = len(scored) or 1
    score = supported / total if scored else 0.0
    return {
        "score": round(score, 3),
        "supported": supported,
        "total": len(scored),
        "method": "token_overlap",
        "sentences": details,
    }


def relevance_score(
    answer: str,
    expected_clause: str,
    contexts: list[str],
    *,
    retrieval_hit5: bool | None,
) -> dict[str, Any]:
    """
    Корректность относительно эталонного пункта:
    - 1.0 если clause упомянут в ответе
    - 0.7 если clause есть в контексте и ответ не пустой / не полный отказ
    - 0.3 если retrieval_hit5 и ответ непустой
    - 0.0 иначе
    """
    if clause_in_text(expected_clause, answer):
        return {"score": 1.0, "reason": "clause_in_answer"}
    ctx_join = "\n".join(contexts)
    has_ctx = clause_in_text(expected_clause, ctx_join)
    nonempty = bool(answer and len(answer.strip()) > 20)
    refusal = bool(
        re.search(
            r"нет (?:в |однозначного ответа)|не\s+найдено|не могу|недостаточно (данных|контекста)|контексте нет",
            answer or "",
            re.I,
        )
    )
    if has_ctx and nonempty and not refusal:
        return {"score": 0.7, "reason": "clause_in_context_answer_ok"}
    if retrieval_hit5 and nonempty and not refusal:
        return {"score": 0.3, "reason": "retrieval_hit5_only"}
    if refusal and not has_ctx and retrieval_hit5 is False:
        return {"score": 0.5, "reason": "honest_refusal_miss"}
    return {"score": 0.0, "reason": "no_clause_signal"}


def load_clause_index(chunked_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Clause → список чанков {text, metadata, id}."""
    index: dict[str, list[dict[str, Any]]] = {}
    if not chunked_dir.is_dir():
        return index
    for path in sorted(chunked_dir.glob("*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                meta = obj.get("metadata") or {}
                clause = (meta.get("Clause") or "").strip()
                if not clause:
                    continue
                rec = {
                    "id": obj.get("id"),
                    "text": obj.get("content") or "",
                    "chapter": meta.get("Chapter") or meta.get("Section") or "",
                    "clause": clause,
                    "source_file": meta.get("source_file"),
                    "score": 1.0,
                }
                index.setdefault(clause, []).append(rec)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warn: skip {path.name}: {exc}", file=sys.stderr)
    return index


def mock_retrieve_and_answer(
    question: str,
    expected_clause: str,
    clause_index: dict[str, list[dict[str, Any]]],
    *,
    hit5: bool | None,
) -> dict[str, Any]:
    """
    Офлайн-симуляция RAG:
    - если hit5 is False → «промах retrieval»: чужой/пустой контекст, честный отказ
    - если hit5 is True или None → берём эталонный чанк как top-1 и «генерим» ответ с цитатой
    """
    gold = clause_index.get(expected_clause) or []
    if hit5 is False:
        # simulate miss: no gold in top-k
        sources: list[dict[str, Any]] = []
        # pick a distractor if any other clause exists
        for cl, recs in clause_index.items():
            if cl != expected_clause and recs:
                sources = [{**recs[0], "score": 0.55}]
                break
        answer = (
            "В предоставленном контексте нет однозначного ответа на вопрос. "
            "Недостаточно данных для ссылки на нужный пункт ПУЭ."
        )
        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "model": "mock-miss",
            "mode": "mock",
        }

    if not gold:
        return {
            "question": question,
            "answer": f"Пункт {expected_clause} не найден в локальных chunked JSONL.",
            "sources": [],
            "model": "mock-missing-chunk",
            "mode": "mock",
        }

    top = gold[0]
    snippet = (top["text"] or "").strip()
    if len(snippet) > 400:
        snippet = snippet[:400] + "…"
    answer = (
        f"Согласно п. {expected_clause} ПУЭ: {snippet} "
        f"(см. пункт {expected_clause})."
    )
    sources = [{**top, "score": 0.92}]
    # add up to 2 more same-clause chunks as extra context
    for extra in gold[1:3]:
        sources.append({**extra, "score": 0.8})
    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "model": "mock-oracle-cite",
        "mode": "mock",
    }


def live_answer(question: str) -> dict[str, Any]:
    from src.rag.rag_service import answer as rag_answer

    result = rag_answer(question)
    result["mode"] = "live"
    return result


def score_one(
    *,
    question: str,
    expected_clause: str,
    answer: str,
    sources: list[dict[str, Any]],
    retrieval_hit5: bool | None,
) -> dict[str, Any]:
    contexts = [(s.get("text") or "") for s in sources]
    cite_answer = clause_in_text(expected_clause, answer)
    cite_context = any(clause_in_text(expected_clause, c) for c in contexts)
    ground = groundedness_score(answer, contexts)
    rel = relevance_score(
        answer, expected_clause, contexts, retrieval_hit5=retrieval_hit5
    )
    return {
        "citation_in_answer": cite_answer,
        "citation_in_context": cite_context,
        "citation": cite_answer or cite_context,
        "groundedness": ground["score"],
        "groundedness_detail": {
            "supported": ground["supported"],
            "total": ground["total"],
            "method": ground["method"],
        },
        "relevance": rel["score"],
        "relevance_reason": rel["reason"],
        "retrieval_hit5": retrieval_hit5,
    }


def try_llm_judge(answer: str, contexts: list[str], question: str) -> dict[str, Any] | None:
    """Опциональный LLM-judge через Ollama (если доступен)."""
    try:
        from src.rag.ollama_client import OllamaClient
    except Exception:
        return None
    client = OllamaClient()
    if not client.health():
        return None
    ctx = "\n\n".join(contexts)[:3500]
    prompt = (
        "Оцени groundedness ответа помощника по шкале 0..1. "
        "1 = все утверждения опираются только на КОНТЕКСТ; 0 = выдумка.\n"
        f"ВОПРОС: {question}\n\nКОНТЕКСТ:\n{ctx}\n\nОТВЕТ:\n{answer}\n\n"
        "Верни только число от 0 до 1."
    )
    try:
        raw = client.generate(prompt, system="Ты строгий оценщик RAG. Отвечай одним числом.")
        m = re.search(r"0?\.\d+|1(?:\.0+)?|0", raw.replace(",", "."))
        if not m:
            return {"raw": raw[:200], "score": None}
        return {"score": float(m.group(0)), "raw": raw[:200], "model": client.config.model}
    except Exception as exc:
        return {"error": str(exc)}


def milvus_up() -> bool:
    try:
        from multimodal_rag import check_vector_db_server
        from runtime_config import load_runtime_config

        cfg = load_runtime_config()
        vdb = cfg["vector_db"]
        return bool(check_vector_db_server(vdb["host"], str(vdb["port"])))
    except Exception:
        return False


def ollama_up() -> bool:
    try:
        from src.rag.ollama_client import OllamaClient

        return OllamaClient().health()
    except Exception:
        return False


def aggregate(details: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(details) or 1
    cite = sum(1 for d in details if d["scores"]["citation"])
    cite_ans = sum(1 for d in details if d["scores"]["citation_in_answer"])
    cite_ctx = sum(1 for d in details if d["scores"]["citation_in_context"])
    ground = sum(d["scores"]["groundedness"] for d in details) / n
    rel = sum(d["scores"]["relevance"] for d in details) / n
    return {
        "n_questions": len(details),
        "citation_rate": round(100.0 * cite / n, 1),
        "citation_in_answer_rate": round(100.0 * cite_ans / n, 1),
        "citation_in_context_rate": round(100.0 * cite_ctx / n, 1),
        "groundedness_avg": round(ground, 3),
        "relevance_avg": round(rel, 3),
        "llm_judge_avg": None,
    }


def run_eval(
    *,
    mode: str,
    limit: int | None,
    out_path: Path,
    use_llm_judge: bool,
    use_hitk: bool,
) -> dict[str, Any]:
    if not QUESTIONS_PATH.is_file():
        raise RuntimeError(f"Нет файла вопросов: {QUESTIONS_PATH}")

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if limit is not None:
        questions = questions[:limit]

    hitk_map: dict[Any, bool] = {}
    if use_hitk and HITK_JSON.is_file():
        hitk = json.loads(HITK_JSON.read_text(encoding="utf-8"))
        for row in hitk.get("details") or []:
            hitk_map[row.get("id")] = bool((row.get("hit") or {}).get("@5"))

    mode_eff = mode
    blockers: list[str] = []
    if mode == "live":
        m_ok, o_ok = milvus_up(), ollama_up()
        if not m_ok:
            blockers.append("Milvus недоступен (localhost:19530). Запустите: python scripts/start_milvus.py")
        if not o_ok:
            blockers.append("Ollama недоступен (localhost:11434). Запустите: python scripts/start_ollama.py --pull")
        if blockers:
            print("LIVE недоступен, переключаюсь на mock:\n  - " + "\n  - ".join(blockers))
            mode_eff = "mock"

    clause_index: dict[str, list[dict[str, Any]]] = {}
    if mode_eff in ("mock", "dry-run"):
        clause_index = load_clause_index(CHUNKED_DIR)
        print(f"Индекс Clause из chunked: {len(clause_index)} пунктов")

    details: list[dict[str, Any]] = []
    llm_scores: list[float] = []

    for item in questions:
        qid = item.get("id")
        q = item["query"]
        expected = item["expected_clause"]
        hit5 = hitk_map.get(qid) if hitk_map else None

        if mode_eff == "live":
            try:
                result = live_answer(q)
            except Exception as exc:
                result = {
                    "question": q,
                    "answer": "",
                    "sources": [],
                    "model": None,
                    "mode": "live-error",
                    "error": str(exc),
                }
        else:
            result = mock_retrieve_and_answer(
                q, expected, clause_index, hit5=hit5
            )

        answer = result.get("answer") or ""
        sources = result.get("sources") or []
        scores = score_one(
            question=q,
            expected_clause=expected,
            answer=answer,
            sources=sources,
            retrieval_hit5=hit5,
        )

        llm_j = None
        if use_llm_judge and mode_eff == "live":
            llm_j = try_llm_judge(answer, [s.get("text") or "" for s in sources], q)
            if llm_j and isinstance(llm_j.get("score"), (int, float)):
                llm_scores.append(float(llm_j["score"]))

        details.append(
            {
                "id": qid,
                "query": q,
                "expected_clause": expected,
                "model": result.get("model"),
                "mode": result.get("mode", mode_eff),
                "answer_preview": answer[:400],
                "n_sources": len(sources),
                "scores": scores,
                "llm_judge": llm_j,
                "error": result.get("error"),
            }
        )
        print(
            f"[{qid}] cite={scores['citation']} "
            f"g={scores['groundedness']:.2f} r={scores['relevance']:.2f} "
            f"hit5={hit5} | {expected}"
        )

    metrics = aggregate(details)
    if llm_scores:
        metrics["llm_judge_avg"] = round(sum(llm_scores) / len(llm_scores), 3)

    out = {
        "evaluated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "mode_requested": mode,
        "mode_effective": mode_eff,
        "source": "eval_rag_generation.py",
        "questions_path": str(QUESTIONS_PATH.relative_to(ROOT)),
        "hitk_aligned": bool(hitk_map),
        "blockers": blockers,
        "metrics": metrics,
        "details": details,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nМетрики: {json.dumps(metrics, ensure_ascii=False)}")
    print(f"Результаты: {out_path}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval RAG generation/citation/groundedness")
    parser.add_argument(
        "--mode",
        choices=("live", "mock", "dry-run"),
        default="live",
        help="live=Milvus+Ollama; mock/dry-run=офлайн по chunked (+hit@k)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Ограничить число вопросов")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Путь JSON результатов (по умолчанию Этапы/Reports/stage4_gen_eval_results.json)",
    )
    parser.add_argument(
        "--no-hitk",
        action="store_true",
        help="Не выравнивать mock по stage4_hitk_results.json",
    )
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Доп. оценка groundedness через Ollama (только live)",
    )
    args = parser.parse_args()
    out = args.out or DEFAULT_OUT
    try:
        run_eval(
            mode=args.mode,
            limit=args.limit,
            out_path=out,
            use_llm_judge=args.llm_judge,
            use_hitk=not args.no_hitk,
        )
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
