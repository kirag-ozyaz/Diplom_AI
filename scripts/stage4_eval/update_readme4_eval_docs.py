# -*- coding: utf-8 -*-
"""Обновляет в Readme-4.md блоки Hit@k и таблицу вопросов из JSON (после eval)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _bootstrap import ROOT, setup_paths  # noqa: E402

setup_paths()
from report_paths import README4_MD, STAGE4_QUESTIONS, rel_from_root  # noqa: E402

MD_PATH = README4_MD

MARK_52_START = "<!-- stage4-eval:5.3:start -->"
MARK_52_END = "<!-- stage4-eval:5.3:end -->"
MARK_52_LEGACY_START = "<!-- stage4-eval:5.2:start -->"
MARK_52_LEGACY_END = "<!-- stage4-eval:5.2:end -->"
MARK_61_START = "<!-- stage4-eval:6.1:start -->"
MARK_61_END = "<!-- stage4-eval:6.1:end -->"
MARK_7_START = "<!-- stage4-eval:7:start -->"
MARK_7_END = "<!-- stage4-eval:7:end -->"


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    if not re.search(pattern, text, flags=re.DOTALL):
        raise SystemExit(f"Markers not found in Readme-4.md: {start} … {end}")
    replacement = f"{start}\n{body}\n{end}"
    return re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)


def refresh_readme4_eval_docs(*, sync_notebook: bool = True) -> None:
    from stage4_hitk_report import (  # noqa: E402
        QUESTIONS_PATH,
        RESULTS_PATH,
        build_section_52_markdown,
        build_section_61_markdown,
        build_section_7_markdown,
        load_questions,
        load_results,
    )

    if not QUESTIONS_PATH.is_file():
        raise SystemExit(f"Нет файла: {QUESTIONS_PATH}")
    questions = load_questions()
    n = len(questions)

    if not RESULTS_PATH.is_file():
        raise SystemExit(
            f"Нет {RESULTS_PATH.name} — сначала: python scripts/stage4_eval/eval_retrieval_hitk.py"
        )
    results = load_results()

    body_52 = build_section_52_markdown(results)
    body_52 = body_52.replace(
        "После изменения вопросов в JSON снова выполните eval.",
        "При добавлении вопросов в JSON снова запустите eval — этот блок обновится автоматически.",
    )

    md = MD_PATH.read_text(encoding="utf-8")
    if MARK_52_START in md:
        md = _replace_block(md, MARK_52_START, MARK_52_END, body_52)
    elif MARK_52_LEGACY_START in md:
        md = _replace_block(md, MARK_52_LEGACY_START, MARK_52_LEGACY_END, body_52)
    else:
        raise SystemExit("Markers §5.3 not found in Readme-4.md")
    md = _replace_block(
        md, MARK_61_START, MARK_61_END, build_section_61_markdown(questions)
    )
    if MARK_7_START in md:
        md = _replace_block(md, MARK_7_START, MARK_7_END, build_section_7_markdown(results))

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
    print(f"Readme-4.md: обновлены §5.3, §6.1, §7, N={n}")

    if sync_notebook:
        import sync_readme4_notebook

        sync_readme4_notebook.main()


if __name__ == "__main__":
    setup_paths()
    refresh_readme4_eval_docs()
