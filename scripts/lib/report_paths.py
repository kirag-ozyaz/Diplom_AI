# -*- coding: utf-8 -*-
"""Пути к отчётам и артефактам этапов (каталог Этапы/Reports)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "Этапы" / "Reports"

ETAP1 = REPORTS / "etap1"
ETAP2 = REPORTS / "etap2"
ETAP3 = REPORTS / "etap3"
ETAP4 = REPORTS / "etap4"

STAGE4_EVAL_SCRIPTS = ROOT / "scripts" / "stage4_eval"
STAGE4_RESULTS = STAGE4_EVAL_SCRIPTS / "results"
RAG_EVAL_QUESTIONS_DIR = ROOT / "data" / "rag_eval_questions"
STAGE4_DATA = RAG_EVAL_QUESTIONS_DIR
STAGE4_RETRIEVAL = STAGE4_RESULTS / "retrieval"
STAGE4_GENERATION = STAGE4_RESULTS / "generation"

STAGE4_QUESTIONS = RAG_EVAL_QUESTIONS_DIR / "eval_questions.json"
STAGE4_QUESTIONS_PUE300 = RAG_EVAL_QUESTIONS_DIR / "eval_questions_pue300.json"
STAGE4_QUESTIONS_BASE38 = RAG_EVAL_QUESTIONS_DIR / "eval_questions_base38.json"
STAGE4_QUESTIONS_SNAPSHOT_74 = RAG_EVAL_QUESTIONS_DIR / "eval_questions_74.json"
STAGE4_HITK_RESULTS = STAGE4_RETRIEVAL / "stage4_hitk_results.json"
STAGE4_HITK_RESULTS_E5 = STAGE4_RETRIEVAL / "stage4_hitk_results_e5.json"
STAGE4_HITK_RESULTS_RERANK = STAGE4_RETRIEVAL / "stage4_hitk_results_rerank.json"
STAGE4_HITK_RUNS = STAGE4_RETRIEVAL / "stage4_hitk_runs.jsonl"
STAGE4_HITK_CHART = STAGE4_RETRIEVAL / "stage4_hitk_chart.png"
STAGE4_HITK_REPORT_PNG = STAGE4_RETRIEVAL / "stage4_hitk_report.png"
STAGE4_RANK_RESULTS_BASE = STAGE4_RETRIEVAL / "stage4_rank_results_base.json"
STAGE4_RANK_RESULTS_E5 = STAGE4_RETRIEVAL / "stage4_rank_results_e5.json"
STAGE4_RANK_RESULTS_RERANK = STAGE4_RETRIEVAL / "stage4_rank_results_rerank.json"
STAGE4_RANK_COMPARISON_MD = STAGE4_RETRIEVAL / "rank_metrics_comparison.md"
STAGE4_RANK_COMPARISON_CSV = STAGE4_RETRIEVAL / "rank_metrics_comparison.csv"
STAGE4_RANK_JSON_BY_MODE = {
    "base": STAGE4_RANK_RESULTS_BASE,
    "e5": STAGE4_RANK_RESULTS_E5,
    "rerank": STAGE4_RANK_RESULTS_RERANK,
}
STAGE4_HITK_JSON_BY_MODE = {
    "base": STAGE4_HITK_RESULTS,
    "e5": STAGE4_HITK_RESULTS_E5,
    "rerank": STAGE4_HITK_RESULTS_RERANK,
}
STAGE4_GEN_RESULTS = STAGE4_GENERATION / "stage4_gen_eval_results.json"
STAGE4_GEN_RESULTS_E5 = STAGE4_GENERATION / "stage4_gen_eval_results_e5.json"
STAGE4_GEN_RESULTS_RERANK = STAGE4_GENERATION / "stage4_gen_eval_results_rerank.json"
STAGE4_PERF_METRICS = STAGE4_GENERATION / "stage4_performance_metrics.json"
STAGE4_PERF_METRICS_E5 = STAGE4_GENERATION / "stage4_performance_metrics_e5.json"
STAGE4_PERF_METRICS_RERANK = STAGE4_GENERATION / "stage4_performance_metrics_rerank.json"
STAGE4_LLM_JUDGE_METRICS = STAGE4_GENERATION / "stage4_llm_judge_metrics.json"
STAGE4_LLM_JUDGE_METRICS_E5 = STAGE4_GENERATION / "stage4_llm_judge_metrics_e5.json"
STAGE4_LLM_JUDGE_METRICS_RERANK = STAGE4_GENERATION / "stage4_llm_judge_metrics_rerank.json"
STAGE4_GEN_METRICS_MD = STAGE4_GENERATION / "Etap4-gen-metrics.md"
STAGE4_METRICS_OVERVIEW_MD = STAGE4_EVAL_SCRIPTS / "Сводка_метрик_этапа_4.md"
README4_MD = ETAP4 / "Readme-4.md"
README4_NB = ETAP4 / "Readme-4 (ver. 2).ipynb"


def rel_from_root(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def md_link(path: Path) -> str:
    return f"`{rel_from_root(path)}`"


def ensure_stage4_result_dirs() -> None:
    for d in (STAGE4_RETRIEVAL, STAGE4_GENERATION):
        d.mkdir(parents=True, exist_ok=True)
