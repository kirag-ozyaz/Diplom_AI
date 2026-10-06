# -*- coding: utf-8 -*-
"""Текст отчёта Hit@k (§5.3, §6.1, §7) из JSON — ноутбук и Readme-4.md."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "Этапы" / "Reports"
QUESTIONS_PATH = REPORTS / "stage4_eval_questions.json"
RESULTS_PATH = REPORTS / "stage4_hitk_results.json"
RUNS_PATH = REPORTS / "stage4_hitk_runs.jsonl"
RESULTS_REL = "`Этапы/Reports/stage4_hitk_results.json`"
RUNS_REL = "`Этапы/Reports/stage4_hitk_runs.jsonl`"


def _short_query(text: str, max_len: int = 58) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text.replace("|", "\\|")
    return (text[: max_len - 3] + "...").replace("|", "\\|")


def hit_counts_from_details(details: list[dict]) -> dict[int, int]:
    counts = {1: 0, 3: 0, 5: 0}
    for row in details:
        hit = row.get("hit") or {}
        for k in counts:
            if hit.get(f"@{k}"):
                counts[k] += 1
    return counts


def format_hit_pct(count: int, n: int) -> str:
    pct = 100.0 * count / n if n else 0.0
    s = f"{pct:.1f}".replace(".", ",")
    return f"**{count} / {n} ({s} %)**"


def evaluated_at_label(results: dict, results_path: Path | None = None) -> str:
    ts = results.get("evaluated_at")
    if ts:
        return str(ts)
    p = results_path or RESULTS_PATH
    if p.is_file():
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        return mtime.strftime("%d.%m.%Y %H:%M") + " (по времени файла JSON)"
    return "—"


def run_summary_from_results(results: dict) -> dict:
    return {
        "evaluated_at": results.get("evaluated_at"),
        "n_questions": results.get("n_questions"),
        "collection": results.get("collection"),
        "collection_num_entities": results.get("collection_num_entities"),
        "text_model": results.get("text_model"),
        "embedding_device": results.get("embedding_device"),
        "metrics_percent": results.get("metrics_percent"),
        "source": results.get("source", "eval_retrieval_hitk.py"),
    }


def append_run_history(results: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    summary = run_summary_from_results(results)
    with RUNS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")


def load_run_history(limit: int = 10) -> list[dict]:
    if not RUNS_PATH.is_file():
        return []
    lines = [ln for ln in RUNS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines[-limit:]]


def format_run_history_markdown(runs: list[dict]) -> str:
    if not runs:
        return ""
    header = (
        "| Прогон (eval) | N | Hit@1 | Hit@3 | Hit@5 | Модель |\n"
        "|---|---:|---:|---:|---:|---|"
    )
    rows = []
    for r in reversed(runs):
        m = r.get("metrics_percent") or {}
        rows.append(
            f"| {r.get('evaluated_at', '—')} | {r.get('n_questions', '—')} | "
            f"{m.get('hit@1', '—')} % | {m.get('hit@3', '—')} % | {m.get('hit@5', '—')} % | "
            f"`{r.get('text_model', '—')}` |"
        )
    return (
        f"\n\n**История прогонов** (каждый вызов `eval_retrieval_hitk.py`, файл {RUNS_REL}):\n\n"
        + header
        + "\n"
        + "\n".join(rows)
    )


def build_section_52_markdown(
    results: dict,
    *,
    results_path: Path | None = None,
    max_hit5_examples: int | None = 8,
) -> str:
    n = int(results["n_questions"])
    details = results["details"]
    counts = hit_counts_from_details(details)
    model = results.get("text_model", "—")
    collection = results.get("collection", "—")
    evaluated = evaluated_at_label(results, results_path)
    metrics = results.get("metrics_percent") or {}

    num_entities = results.get("collection_num_entities")
    coll_line = f"Коллекция: `{collection}`"
    if num_entities is not None:
        coll_line += f", **{num_entities}** записей в Milvus"
    coll_line += f". Модель при оценке: `{model}`."

    device = results.get("embedding_device")
    device_line = ""
    if device:
        device_line = f"Inference эмбеддингов при прогоне eval: **{device}**."

    hit5_ok = [row["id"] for row in details if (row.get("hit") or {}).get("@5")]
    hit5_miss = [row["id"] for row in details if not (row.get("hit") or {}).get("@5")]
    if max_hit5_examples is None or max_hit5_examples >= len(hit5_ok):
        examples = ", ".join(f"id {i}" for i in hit5_ok) or "—"
    else:
        examples = ", ".join(f"id {i}" for i in hit5_ok[:max_hit5_examples])
        if len(hit5_ok) > max_hit5_examples:
            examples += f" … (всего {len(hit5_ok)})"

    scores_hit5 = [
        row["top1_score"]
        for row in details
        if (row.get("hit") or {}).get("@5") and row.get("top1_score") is not None
    ]
    scores_miss = [
        row["top1_score"]
        for row in details
        if not (row.get("hit") or {}).get("@5") and row.get("top1_score") is not None
    ]
    score_note = ""
    if scores_hit5 and scores_miss:
        score_note = (
            f"Средний cosine top-1: при Hit@5 **{mean(scores_hit5):.3f}**, "
            f"при промахе Hit@5 **{mean(scores_miss):.3f}**."
        )

    lines = [
        "**Источник:** только последний прогон **`scripts/eval_retrieval_hitk.py`** "
        "(Milvus + SentenceTransformer, поле `details` в JSON). **Ollama / LLM не используются.** "
        "Текст §5.3 — автоматическое форматирование чисел из JSON, не генерация ответа моделью.",
        "",
        coll_line,
        f"Последний прогон: **{evaluated}** (`python scripts/eval_retrieval_hitk.py`).",
    ]
    if device_line:
        lines.append(device_line)
    lines.extend(
        [
            f"Число запросов *N* — из `stage4_eval_questions.json`; метрики — из {RESULTS_REL}.",
            f"Полный JSON: {RESULTS_REL}.",
            "",
            "| Метрика | Значение | Комментарий |",
            "|---------|----------|-------------|",
            f"| Hit@1 | {format_hit_pct(counts[1], n)} | Эталонный пункт на 1-м месте |",
            f"| Hit@3 | {format_hit_pct(counts[3], n)} | Эталонный пункт в top-3 |",
            f"| Hit@5 | {format_hit_pct(counts[5], n)} | Эталонный пункт в top-5 |",
            f"| Число запросов | **{n}** | `stage4_eval_questions.json` |",
        ]
    )
    if metrics:
        lines.append(
            f"| Сводка JSON | Hit@1 {metrics.get('hit@1', '—')} %, "
            f"Hit@3 {metrics.get('hit@3', '—')} %, Hit@5 {metrics.get('hit@5', '—')} % | "
            "`metrics_percent` в JSON |"
        )
    lines.extend(
        [
            "",
            f"Примеры успешных Hit@5: {examples}.",
            f"Промахи Hit@5: **{len(hit5_miss)}** вопросов (id: {', '.join(str(i) for i in hit5_miss) or '—'}).",
        ]
    )
    if score_note:
        lines.append(score_note)
    lines.append(format_run_history_markdown(load_run_history(8)))
    lines.append("")
    lines.append(
        "После изменения вопросов в JSON снова выполните eval — блок обновится автоматически."
    )
    return "\n".join(lines)


def build_section_7_markdown(results: dict) -> str:
    """§7 Выводы — с актуальными N и Hit@k из последнего прогона."""
    n = int(results.get("n_questions") or len(results.get("details") or []))
    m = results.get("metrics_percent") or {}
    h1, h3, h5 = (m.get("hit@1"), m.get("hit@3"), m.get("hit@5"))
    eval_at = evaluated_at_label(results)
    hit_line = ""
    if h1 is not None and h3 is not None and h5 is not None:
        hit_line = (
            f" На прогоне **{eval_at}**: Hit@1 **{h1}%**, Hit@3 **{h3}%**, Hit@5 **{h5}%** "
            f"(`eval_retrieval_hitk.py`, {RESULTS_REL})."
        )
    return "\n".join(
        [
            "1. **База ПУЭ** подготовлена и проиндексирована; **прототип рабочего контура RAG** "
            "опирается на чанки с метаданными пунктов.",
            "2. **Retrieval** — **SentenceTransformer + Milvus** (`search_text`) — реализован; "
            "конфиг `rag_runtime.json`.",
            f"3. **Первая измеримая точность** — **Hit@k** ({n} вопросов, один поиск на вопрос); "
            f"скрипт `eval_retrieval_hitk.py` и график.{hit_line}",
            "4. **Generation** — **Ollama** в `src/rag/rag_service.py`; Telegram-бот — этап 5.",
            "5. Ограничения: промахи retrieval; LLM — только при опоре на top-k контекст.",
        ]
    )


def build_section_61_markdown(questions: list[dict]) -> str:
    header = (
        "| № | Вопрос (кратко) | Эталон Clause |\n"
        "|---|-----------------|---------------|"
    )
    rows = [
        f"| {item.get('id', '?')} | {_short_query(item['query'])} | {item['expected_clause']} |"
        for item in questions
    ]
    return header + "\n" + "\n".join(rows)


def load_results(path: Path | None = None) -> dict:
    p = path or RESULTS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def load_questions(path: Path | None = None) -> list[dict]:
    p = path or QUESTIONS_PATH
    return json.loads(p.read_text(encoding="utf-8"))
