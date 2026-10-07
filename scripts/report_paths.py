# -*- coding: utf-8 -*-
"""Пути к отчётам и артефактам этапов (Этапы/Reports)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "Этапы" / "Reports"

ETAP1 = REPORTS / "etap1"
ETAP2 = REPORTS / "etap2"
ETAP3 = REPORTS / "etap3"
ETAP4 = REPORTS / "etap4"

STAGE4_DATA = ETAP4 / "data"
STAGE4_RETRIEVAL = ETAP4 / "retrieval"
STAGE4_GENERATION = ETAP4 / "generation"

STAGE4_QUESTIONS = STAGE4_DATA / "stage4_eval_questions.json"
STAGE4_HITK_RESULTS = STAGE4_RETRIEVAL / "stage4_hitk_results.json"
STAGE4_HITK_RUNS = STAGE4_RETRIEVAL / "stage4_hitk_runs.jsonl"
STAGE4_HITK_CHART = STAGE4_RETRIEVAL / "stage4_hitk_chart.png"
STAGE4_HITK_REPORT_PNG = STAGE4_RETRIEVAL / "stage4_hitk_report.png"
STAGE4_GEN_RESULTS = STAGE4_GENERATION / "stage4_gen_eval_results.json"
STAGE4_GEN_METRICS_MD = STAGE4_GENERATION / "Etap4-gen-metrics.md"

README4_MD = ETAP4 / "Readme-4.md"
README4_NB = ETAP4 / "Readme-4 (ver. 2).ipynb"


def rel_from_root(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def md_link(path: Path) -> str:
    return f"`{rel_from_root(path)}`"
