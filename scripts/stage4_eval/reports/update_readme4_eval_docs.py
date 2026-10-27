# -*- coding: utf-8 -*-
"""Обновляет в Readme-4.md блоки Hit@k и таблицу вопросов из JSON (после eval)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _bootstrap import ROOT, setup_paths  # noqa: E402

setup_paths()
from report_paths import (  # noqa: E402
    README4_MD,
    STAGE4_GEN_RESULTS,
    STAGE4_LLM_JUDGE_METRICS,
    STAGE4_PERF_METRICS,
    STAGE4_QUESTIONS,
    rel_from_root,
)

MD_PATH = README4_MD

MARK_52_START = "<!-- stage4-eval:5.3:start -->"
MARK_52_END = "<!-- stage4-eval:5.3:end -->"
MARK_52_LEGACY_START = "<!-- stage4-eval:5.2:start -->"
MARK_52_LEGACY_END = "<!-- stage4-eval:5.2:end -->"
MARK_61_START = "<!-- stage4-eval:6.1:start -->"
MARK_61_END = "<!-- stage4-eval:6.1:end -->"
MARK_54_START = "<!-- stage4-eval:5.4:start -->"
MARK_54_END = "<!-- stage4-eval:5.4:end -->"
MARK_7_START = "<!-- stage4-eval:7:start -->"
MARK_7_END = "<!-- stage4-eval:7:end -->"


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    if not re.search(pattern, text, flags=re.DOTALL):
        raise SystemExit(f"Markers not found in Readme-4.md: {start} … {end}")
    replacement = f"{start}\n{body}\n{end}"
    return re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)


def refresh_readme4_eval_docs(*, sync_notebook: bool = True) -> None:
    mrr_ndcg = Path(__file__).resolve().parents[1] / "retrieval" / "mrr_ndcg"
    sys.path.insert(0, str(mrr_ndcg))
    try:
        from rank_metrics import refresh_rank_comparison  # noqa: E402

        refresh_rank_comparison()
    except Exception:
        pass

    from stage4_hitk_report import (  # noqa: E402
        QUESTIONS_PATH,
        RESULTS_PATH,
        build_section_52_markdown,
        build_section_54_markdown,
        build_section_61_markdown,
        build_section_7_markdown,
        load_optional_json,
        load_questions,
        load_results,
    )

    if not QUESTIONS_PATH.is_file():
        raise SystemExit(f"Нет файла: {QUESTIONS_PATH}")
    questions = load_questions()
    n = len(questions)

    if not RESULTS_PATH.is_file():
        raise SystemExit(
            f"Нет {RESULTS_PATH.name} — сначала: python scripts/stage4_eval/retrieval/eval_retrieval_hitk.py"
        )
    results = load_results()
    gen = load_optional_json(STAGE4_GEN_RESULTS)
    perf = load_optional_json(STAGE4_PERF_METRICS)
    judge = load_optional_json(STAGE4_LLM_JUDGE_METRICS)

    body_52 = build_section_52_markdown(results)
    body_52 = body_52.replace(
        "После изменения вопросов в JSON снова выполните eval.",
        "При добавлении вопросов в JSON снова запустите eval — этот блок обновится автоматически.",
    )

    md = MD_PATH.read_text(encoding="utf-8")
    has_54 = MARK_54_START in md
    if MARK_52_START in md:
        md = _replace_block(md, MARK_52_START, MARK_52_END, body_52)
    elif MARK_52_LEGACY_START in md:
        md = _replace_block(md, MARK_52_LEGACY_START, MARK_52_LEGACY_END, body_52)
    else:
        raise SystemExit("Markers §5.3 not found in Readme-4.md")
    md = _replace_block(
        md, MARK_61_START, MARK_61_END, build_section_61_markdown(questions)
    )
    if MARK_54_START in md:
        md = _replace_block(
            md,
            MARK_54_START,
            MARK_54_END,
            build_section_54_markdown(results, gen=gen, perf=perf, judge=judge),
        )
    if MARK_7_START in md:
        md = _replace_block(
            md,
            MARK_7_START,
            MARK_7_END,
            build_section_7_markdown(results, gen=gen, perf=perf, judge=judge),
        )

    md = re.sub(r"\*\*Дата отчёта:\*\* \d{2}\.\d{2}\.\d{4}\.", "**Дата отчёта:** 18.10.2026.", md, count=1)
    md = re.sub(
        r"Реестр \*\*\d+\*\* контрольных вопросов",
        f"Реестр **{n}** контрольных вопросов",
        md,
    )
    md = re.sub(
        r"Контрольный набор из \*\*\d+\*\* вопросов",
        f"Контрольный набор из **{n}** вопросов",
        md,
        count=1,
    )
    md = re.sub(
        r"Контрольный набор для расчёта — \*\*\d+\*\* вопросов",
        f"Контрольный набор для расчёта — **{n}** вопросов",
        md,
        count=1,
    )
    md = re.sub(r"(\*N\* = )\d+", rf"\g<1>{n}", md, count=1)
    md = re.sub(
        rf"(\| `{rel_from_root(STAGE4_QUESTIONS).replace('/', r'/')}` \| )\d+( тестовых вопросов)",
        rf"\g<1>{n}\2",
        md,
        count=1,
    )
    md = re.sub(
        r"(\*\*Hit@k\*\* \()\d+( вопросов, один поиск)",
        rf"\g<1>{n}\2",
        md,
        count=1,
    )

    MD_PATH.write_text(md, encoding="utf-8")
    parts = ["§5.3", "§6.1"]
    if has_54:
        parts.append("§5.4")
    parts.append("§7")
    print(f"Readme-4.md: обновлены {', '.join(parts)}, N={n}")

    if sync_notebook:
        reports_scripts = ROOT / "scripts" / "reports"
        if str(reports_scripts) not in sys.path:
            sys.path.insert(0, str(reports_scripts))
        import sync_readme4_notebook

        sync_readme4_notebook.main()


if __name__ == "__main__":
    setup_paths()
    refresh_readme4_eval_docs()
