# -*- coding: utf-8 -*-
"""
Сводка метрик этапа 4 по трём опытам из JSON-результатов (без Milvus и Ollama).

Читает scripts/stage4_eval/results/{retrieval,generation}/ и пишет:
  results/stage4_summary.md   — сводные таблицы для отчёта
  results/stage4_summary.csv  — та же сводка в длинном формате (опыт, слой, метрика, значение, источник, дата)
  results/stage4_summary.json — то же в JSON

Проверки: полнота прогона generation (N = N вопросов в Hit@k, нет partial_run),
совпадение Hit@1/3/5 в stage4_hitk_results*.json и stage4_rank_results_*.json,
citation_in_context_rate = Hit@5. Найденные проблемы выводятся в раздел «Проверки».

Запуск из корня проекта:
  python scripts/stage4_eval/reports/build_stage4_summary.py
  python scripts/stage4_eval/reports/build_stage4_summary.py --root X:/path/to/project --strict
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

EXPERIMENTS = [
    # (номер в отчёте, подпись, суффикс JSON hitk/gen/perf/judge, режим rank)
    (1, "Опыт 1 (база)", "", "base"),
    (2, "Опыт 2 (E5)", "_e5", "e5"),
    (3, "Опыт 3 (реранкер)", "_rerank", "rerank"),
]


def load(p: Path):
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8-sig"))


def fmt(v, d=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{d}f}".replace(".", ",")
    return str(v)


def collect(root: Path):
    res = root / "scripts" / "stage4_eval" / "results"
    rdir, gdir = res / "retrieval", res / "generation"
    rows, checks, exps = [], [], []
    for num, label, suf, mode in EXPERIMENTS:
        e = {"num": num, "label": label}
        hk = load(rdir / f"stage4_hitk_results{suf}.json")
        rk = load(rdir / f"stage4_rank_results_{mode}.json")
        gen = load(gdir / f"stage4_gen_eval_results{suf}.json")
        perf = load(gdir / f"stage4_performance_metrics{suf}.json")
        judge = load(gdir / f"stage4_llm_judge_metrics{suf}.json")

        def add(layer, metric, value, src, when):
            rows.append({"experiment": num, "label": label, "layer": layer, "metric": metric,
                         "value": value, "source": src, "evaluated_at": when})
            e.setdefault(layer, {})[metric] = value

        n = None
        if hk:
            n = hk.get("n_questions")
            src = f"retrieval/stage4_hitk_results{suf}.json"
            for k in ("hit@1", "hit@3", "hit@5"):
                add("hitk", k, hk["metrics_percent"][k], src, hk.get("evaluated_at"))
            add("hitk", "n", n, src, hk.get("evaluated_at"))
            add("hitk", "miss@5", sum(1 for d in hk.get("details", []) if not d["hit"]["@5"]), src, hk.get("evaluated_at"))
        else:
            checks.append(f"{label}: нет stage4_hitk_results{suf}.json")
        if rk:
            m = rk["metrics"]
            src = f"retrieval/stage4_rank_results_{mode}.json"
            for k in ("hit@10", "mrr", "mrr@3", "mrr@5", "ndcg@3", "ndcg@5", "ndcg@10"):
                if k in m:
                    add("rank", k, m[k], src, rk.get("evaluated_at"))
            durs = [d.get("duration_sec") for d in rk.get("details", []) if d.get("duration_sec") is not None]
            if durs:
                add("time", "retrieval_sec_avg", sum(durs) / len(durs), src, rk.get("evaluated_at"))
            if hk:
                for k in ("hit@1", "hit@3", "hit@5"):
                    a, b = hk["metrics_percent"][k], round(m[k] * 100, 1)
                    if abs(a - b) > 0.05:
                        checks.append(f"{label}: {k} в hitk ({a}) и rank ({b}) не совпадают")
        else:
            checks.append(f"{label}: нет stage4_rank_results_{mode}.json (MRR/nDCG)")
        if gen:
            gm = gen.get("metrics", {})
            src = f"generation/stage4_gen_eval_results{suf}.json"
            gn = gm.get("n_questions")
            partial = bool(gm.get("partial_run")) or (n is not None and gn != n)
            for k in ("citation_rate", "citation_in_answer_rate", "citation_in_context_rate",
                      "groundedness_avg", "relevance_avg"):
                add("generation", k, gm.get(k), src, gen.get("evaluated_at"))
            add("generation", "n", gn, src, gen.get("evaluated_at"))
            add("time", "rag_sec_avg", gm.get("duration_avg_sec"), src, gen.get("evaluated_at"))
            errs = sum(1 for d in gen.get("details", []) if d.get("error"))
            add("generation", "errors", errs, src, gen.get("evaluated_at"))
            e["gen_partial"] = partial
            if partial:
                checks.append(f"{label}: generation — НЕПОЛНЫЙ прогон ({gn} из {n} вопросов, "
                              f"{gen.get('evaluated_at')}); файл {src} перезаписан, нужен повторный полный прогон")
            elif hk and gm.get("citation_in_context_rate") is not None and \
                    abs(gm["citation_in_context_rate"] - hk["metrics_percent"]["hit@5"]) > 0.05:
                checks.append(f"{label}: citation_in_context_rate ({gm['citation_in_context_rate']}) ≠ Hit@5 "
                              f"({hk['metrics_percent']['hit@5']})")
        else:
            checks.append(f"{label}: нет stage4_gen_eval_results{suf}.json")
        if perf:
            pm = perf.get("metrics", {})
            src = f"generation/stage4_performance_metrics{suf}.json"
            for k in ("ttft_avg_sec", "latency_avg_sec", "latency_p95_sec", "latency_p99_sec", "tps_avg"):
                add("perf", k, pm.get(k), src, perf.get("timestamp"))
            add("perf", "rps", perf.get("rps"), src, perf.get("timestamp"))
            add("perf", "availability_pct", perf.get("availability_pct"), src, perf.get("timestamp"))
            add("perf", "requests", f"{perf.get('successful_requests')}/{perf.get('total_requests')}", src, perf.get("timestamp"))
        if judge:
            sm = judge.get("summary_metrics", {})
            src = f"generation/stage4_llm_judge_metrics{suf}.json"
            for k in ("faithfulness_avg", "answer_relevancy_avg", "context_recall_avg"):
                add("judge", k, sm.get(k), src, judge.get("timestamp"))
            add("judge", "n", judge.get("sample_count"), src, judge.get("timestamp"))
            bad = [d.get("id") for d in judge.get("details", [])
                   if "Ошибка вызова" in str((d.get("scores") or {}).get("reasoning", ""))]
            add("judge", "failed", len(bad), src, judge.get("timestamp"))
            if bad:
                checks.append(f"{label}: LLM-judge — сбой вызова для id {bad} (в среднее вошли нули)")
        exps.append(e)
    return rows, checks, exps


def table(title, exps, layer, metrics, d=3, pct=False):
    head = "| Метрика | " + " | ".join(e["label"] for e in exps) + " |"
    out = [f"### {title}", "", head, "|" + "---|" * (len(exps) + 1)]
    for key, name in metrics:
        vals = []
        for e in exps:
            v = e.get(layer, {}).get(key)
            if key.endswith("_rate") and isinstance(v, (int, float)):
                s = fmt(float(v), 1)
            elif pct and isinstance(v, (int, float)) and key not in ("n", "miss@5", "errors"):
                s = fmt(float(v), 1) + " %"
            else:
                s = fmt(v, d)
            if e.get("gen_partial") and (layer == "generation" or key == "rag_sec_avg"):
                s += " ⚠"
            vals.append(s)
        out.append(f"| {name} | " + " | ".join(vals) + " |")
    return "\n".join(out) + "\n"


def build_md(rows, checks, exps):
    when = lambda layer: ", ".join(sorted({f"{r['label'].split(' (')[0]}: {r['evaluated_at']}"
                                           for r in rows if r["layer"] == layer}))
    md = [f"# Сводка метрик этапа 4 (автоматически, {datetime.now():%d.%m.%Y %H:%M})", "",
          "Источник: `scripts/stage4_eval/results/`. Скрипт: `build_stage4_summary.py`. Не редактировать вручную.", ""]
    md.append(table("Hit@k (retrieval)", exps, "hitk",
                    [("hit@1", "Hit@1"), ("hit@3", "Hit@3"), ("hit@5", "Hit@5"), ("miss@5", "Промахов Hit@5"), ("n", "N")], pct=True))
    md.append(f"Даты: {when('hitk')}\n")
    md.append(table("MRR и nDCG@k (глубина 10)", exps, "rank",
                    [("hit@10", "Hit@10"), ("mrr", "MRR"), ("mrr@3", "MRR@3"), ("mrr@5", "MRR@5"),
                     ("ndcg@3", "nDCG@3"), ("ndcg@5", "nDCG@5"), ("ndcg@10", "nDCG@10")]))
    md.append(f"Даты: {when('rank')}\n")
    md.append(table("Генерация (live)", exps, "generation",
                    [("citation_rate", "citation_rate, %"), ("citation_in_answer_rate", "citation_in_answer_rate, %"),
                     ("citation_in_context_rate", "citation_in_context_rate, %"), ("groundedness_avg", "groundedness_avg"),
                     ("relevance_avg", "relevance_avg"), ("n", "N"), ("errors", "Ошибок live")]))
    md.append(f"Даты: {when('generation')}\n")
    md.append(table("Время", exps, "time", [("rag_sec_avg", "Полный RAG, с/вопрос (generation)"),
                                            ("retrieval_sec_avg", "Retrieval, с/вопрос (rank-прогон, с холодным стартом)")], d=2))
    md.append(table("Нагрузочный тест Ollama", exps, "perf",
                    [("ttft_avg_sec", "TTFT avg, с"), ("latency_avg_sec", "Latency avg, с"), ("latency_p95_sec", "Latency p95, с"),
                     ("latency_p99_sec", "Latency p99, с"), ("tps_avg", "TPS, ток/с"), ("rps", "RPS"),
                     ("availability_pct", "Доступность, %"), ("requests", "Успешно")], d=2))
    md.append(table("LLM-as-a-Judge", exps, "judge",
                    [("faithfulness_avg", "Faithfulness"), ("answer_relevancy_avg", "Answer relevancy"),
                     ("context_recall_avg", "Context recall"), ("n", "N"), ("failed", "Сбоев судьи")], d=4))
    md.append("### Проверки\n")
    md += [f"- {c}" for c in checks] or ["- замечаний нет"]
    md.append("\n⚠ — значение из неполного прогона, в отчёт не переносить.")
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3],
                    help="корень проекта (по умолчанию — три уровня выше скрипта)")
    ap.add_argument("--out-dir", type=Path, default=None, help="куда писать (по умолчанию results/)")
    ap.add_argument("--strict", action="store_true", help="код выхода 1, если есть замечания в «Проверках»")
    a = ap.parse_args()
    rows, checks, exps = collect(a.root)
    out = a.out_dir or (a.root / "scripts" / "stage4_eval" / "results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "stage4_summary.md").write_text(build_md(rows, checks, exps), encoding="utf-8")
    with open(out / "stage4_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["experiment"], delimiter=";")
        w.writeheader(); w.writerows(rows)
    (out / "stage4_summary.json").write_text(json.dumps({"rows": rows, "checks": checks}, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    print(f"Сохранено: {out / 'stage4_summary.md'}, .csv, .json; строк {len(rows)}, замечаний {len(checks)}")
    for c in checks:
        print("  !", c)
    if a.strict and checks:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
