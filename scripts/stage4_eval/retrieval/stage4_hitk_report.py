# -*- coding: utf-8 -*-
"""Текст отчёта Hit@k (§5.3, §6.1, §7) из JSON — ноутбук и Readme-4.md."""
from __future__ import annotations

import json
from datetime import datetime
from statistics import mean

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _bootstrap import setup_paths  # noqa: E402

setup_paths()
from report_paths import (  # noqa: E402
    REPORTS,
    STAGE4_GEN_RESULTS,
    STAGE4_HITK_RESULTS,
    STAGE4_HITK_RUNS,
    STAGE4_LLM_JUDGE_METRICS,
    STAGE4_PERF_METRICS,
    STAGE4_QUESTIONS,
    md_link,
)

QUESTIONS_REL = md_link(STAGE4_QUESTIONS)

QUESTIONS_PATH = STAGE4_QUESTIONS
RESULTS_PATH = STAGE4_HITK_RESULTS
RUNS_PATH = STAGE4_HITK_RUNS
RESULTS_REL = md_link(STAGE4_HITK_RESULTS)
RUNS_REL = md_link(STAGE4_HITK_RUNS)


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
        "**Источник:** только последний прогон **`scripts/stage4_eval/retrieval/eval_retrieval_hitk.py`** "
        "(Milvus + SentenceTransformer, поле `details` в JSON). **Ollama / LLM не используются.** "
        "Текст §5.3 — автоматическое форматирование чисел из JSON, не генерация ответа моделью.",
        "",
        coll_line,
        f"Последний прогон: **{evaluated}** (`python scripts/stage4_eval/retrieval/eval_retrieval_hitk.py`).",
    ]
    if device_line:
        lines.append(device_line)
    lines.extend(
        [
            f"Число запросов *N* — поле `n_questions` в реестре {QUESTIONS_REL}; "
            f"метрики прогона — из {RESULTS_REL}.",
            f"Полный JSON: {RESULTS_REL}.",
            "",
            "| Метрика | Значение | Комментарий |",
            "|---------|----------|-------------|",
            f"| Hit@1 | {format_hit_pct(counts[1], n)} | Эталонный пункт на 1-м месте |",
            f"| Hit@3 | {format_hit_pct(counts[3], n)} | Эталонный пункт в top-3 |",
            f"| Hit@5 | {format_hit_pct(counts[5], n)} | Эталонный пункт в top-5 |",
            f"| Число запросов | **{n}** | {QUESTIONS_REL} |",
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
        "После изменения реестра контрольных вопросов снова выполните прогон оценки — "
        "блок обновится автоматически."
    )
    return "\n".join(lines)


def _pct_count(n: int, rate_pct: float | int | None) -> str:
    if rate_pct is None or not n:
        return "—"
    count = round(n * float(rate_pct) / 100.0)
    s = f"{float(rate_pct):.1f}".replace(".", ",")
    return f"**{s} %** ({count}/{n})"


def _fmt_num(value: float | int | None, *, decimals: int = 2) -> str:
    if value is None:
        return "—"
    s = f"{float(value):.{decimals}f}".replace(".", ",")
    return f"**{s}**"


def build_section_54_markdown(
    hitk: dict,
    *,
    gen: dict | None = None,
    perf: dict | None = None,
    judge: dict | None = None,
) -> str:
    """§5.4 — сводная таблица всех слоёв метрик из JSON артефактов."""
    n = int(hitk.get("n_questions") or len(hitk.get("details") or []))
    counts = hit_counts_from_details(hitk.get("details") or [])
    m = hitk.get("metrics_percent") or {}
    eval_hitk = evaluated_at_label(hitk)

    gen_at = (gen or {}).get("evaluated_at", "—")
    perf_at = (perf or {}).get("timestamp", "—")
    judge_at = (judge or {}).get("timestamp", "—")
    ollama_model = None
    if gen:
        details = gen.get("details") or []
        if details:
            ollama_model = details[0].get("model")
    if not ollama_model and judge:
        ollama_model = judge.get("judge_model")

    intro = (
        f"**Сводная таблица** — полный прогон `run_all.ps1`, *N* = **{n}** вопросов "
        f"(реестр {QUESTIONS_REL}); retrieval **{eval_hitk}**"
    )
    if gen:
        intro += f", generation live **{gen_at}**"
    if perf:
        intro += f", performance **{perf_at}**"
    if judge:
        intro += f", LLM-judge **{judge_at}**"
    intro += f". Ollama: `{ollama_model or 'см. config/rag_runtime.json'}`. Артефакты: `scripts/stage4_eval/results/`.\n\n"
    intro += (
        "| Слой | Метрика | Факт (прогон) | Артефакт / скрипт |\n"
        "|------|---------|---------------|-------------------|\n"
    )

    rows = [
        f"| Retrieval | Hit@1 | {format_hit_pct(counts[1], n)} | "
        f"`retrieval/stage4_hitk_results.json`, `eval_retrieval_hitk.py` |",
        f"| Retrieval | Hit@3 | {format_hit_pct(counts[3], n)} | то же |",
        f"| Retrieval | Hit@5 | {format_hit_pct(counts[5], n)} | то же |",
    ]

    if gen:
        gm = gen.get("metrics") or {}
        gn = int(gm.get("n_questions") or n)
        rows.extend(
            [
                f"| Generation (live) | Citation rate | "
                f"{_pct_count(gn, gm.get('citation_rate'))} | "
                f"`generation/stage4_gen_eval_results.json`, `eval_rag_generation.py` |",
                f"| Generation (live) | Citation в ответе | "
                f"{_pct_count(gn, gm.get('citation_in_answer_rate'))} | то же |",
                f"| Generation (live) | Groundedness | "
                f"{_fmt_num(gm.get('groundedness_avg'))} | то же |",
                f"| Generation (live) | Relevance | "
                f"{_fmt_num(gm.get('relevance_avg'))} | то же |",
            ]
        )
    else:
        rows.append(
            "| Generation (live) | — | *нет JSON* | `eval_rag_generation.py --mode live` |"
        )

    if judge:
        jm = judge.get("summary_metrics") or {}
        rows.extend(
            [
                f"| LLM-as-a-Judge | Faithfulness | "
                f"{_fmt_num(jm.get('faithfulness_avg'), decimals=4)} | "
                f"`generation/stage4_llm_judge_metrics.json`, `eval_rag_llm_judge.py` |",
                f"| LLM-as-a-Judge | Answer relevancy | "
                f"{_fmt_num(jm.get('answer_relevancy_avg'), decimals=4)} | то же |",
                f"| LLM-as-a-Judge | Context recall | "
                f"{_fmt_num(jm.get('context_recall_avg'), decimals=4)} | то же |",
            ]
        )

    if perf:
        pm = perf.get("metrics") or {}
        rows.extend(
            [
                f"| Operations | TTFT (среднее) | "
                f"{_fmt_num(pm.get('ttft_avg_sec'))} с | "
                f"`generation/stage4_performance_metrics.json`, `eval_rag_performance.py` |",
                f"| Operations | TPS (среднее) | "
                f"{_fmt_num(pm.get('tps_avg'))} ток/с | то же |",
                f"| Operations | Latency p95 | "
                f"{_fmt_num(pm.get('latency_p95_sec'))} с | то же |",
                f"| Operations | RPS | "
                f"{_fmt_num(perf.get('rps'))} зап/с | то же |",
                f"| Operations | Availability | "
                f"**{perf.get('availability_pct', '—')} %** | то же |",
            ]
        )

    note = (
        "\n\nMRR и nDCG@5 в текущих скриптах **не рассчитываются** (только Hit@1/3/5). "
        "Нагрузочный тест performance — упрощённый промпт к Ollama (см. `pipeline_note` в JSON), "
        "не latency полного RAG."
    )
    if gen and gen.get("mode_effective") != "live":
        note += (
            f" Режим generation в JSON: `{gen.get('mode_effective')}` "
            f"(запрошен `{gen.get('mode_requested', '—')}`)."
        )
    return intro + "\n".join(rows) + note


def build_section_7_markdown(
    results: dict,
    *,
    gen: dict | None = None,
    perf: dict | None = None,
    judge: dict | None = None,
) -> str:
    """§7 Выводы — Hit@k и при наличии JSON — generation / performance / judge."""
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
    lines = [
        "1. **База ПУЭ** подготовлена и проиндексирована; **прототип рабочего контура RAG** "
        "опирается на чанки с метаданными пунктов.",
        "2. **Retrieval** — **SentenceTransformer + Milvus** (`search_text`) — реализован; "
        "конфиг `rag_runtime.json`.",
        f"3. **Первая измеримая точность** — **Hit@k** ({n} вопросов, один поиск на вопрос); "
        f"скрипт `eval_retrieval_hitk.py` и график.{hit_line}",
    ]
    if gen:
        gm = gen.get("metrics") or {}
        lines.append(
            "4. **Generation (live RAG)** — `eval_rag_generation.py` + `src/rag/rag_service.py`: "
            f"citation **{gm.get('citation_rate', '—')}%**, groundedness **{gm.get('groundedness_avg', '—')}**, "
            f"relevance **{gm.get('relevance_avg', '—')}** "
            f"({gen.get('evaluated_at', '—')}, {md_link(STAGE4_GEN_RESULTS)})."
        )
    else:
        lines.append(
            "4. **Generation** — **Ollama** в `src/rag/rag_service.py`; полный прогон live — "
            "`eval_rag_generation.py`; Telegram-бот — этап 5."
        )
    extra = []
    if perf:
        extra.append(
            f"availability **{perf.get('availability_pct')}%**, RPS **{perf.get('rps')}** "
            f"(TTFT avg **{perf.get('metrics', {}).get('ttft_avg_sec')}** с)"
        )
    if judge:
        jm = judge.get("summary_metrics") or {}
        extra.append(
            f"LLM-judge faithfulness **{jm.get('faithfulness_avg')}** "
            f"({judge.get('timestamp', '—')})"
        )
    if extra:
        lines.append("5. **Эксплуатация и качество (доп.)** — " + "; ".join(extra) + ".")
        lines.append(
            "6. **Ограничения:** промахи retrieval; LLM — только при опоре на top-k; "
            "judge использует шаблонный контекст (см. `scripts/stage4_eval/docs/Сводка_метрик_этапа_4.md`)."
        )
    else:
        lines.append(
            "5. **Ограничения:** промахи retrieval; LLM — только при опоре на top-k контекст."
        )
    return "\n".join(lines)


def load_optional_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
    from eval_questions_io import load_eval_questions  # noqa: E402

    p = path or QUESTIONS_PATH
    return load_eval_questions(p)
