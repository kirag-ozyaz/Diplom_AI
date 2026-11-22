"""Сборка папки data_V2 для ноутбука Etap4_V2.ipynb (этап 4, вторая версия).

Запуск из корня репозитория Diplom_AI:
    python V2/scripts/collect_data_V2.py
    python V2/scripts/collect_data_V2.py --out D:/tmp/data_V2

Что копируется (исходные файлы не меняются, retrieval.json и журналы не копируются):
  - metrics.json последнего прогона каждого опыта (1-5 и контроль) из V2/results/retrieval/split*;
    опыт определяется по настройкам внутри metrics.json, учитываются только прогоны на 720 вопросах
    с qrels_version = split-720-exact-text-v1;
  - последние папки *_rerank50 и *_refusal в V2/results/generation/answers и judge;
  - вопросы и эталон: V2/data/rag_eval_questions/eval_questions_split.json, eval_qrels_split.json,
    eval_questions_refusal.json;
  - корпус V2/data/chunked_merged_manual/*.chunked.jsonl (без изображений);
  - результаты поиска V1 для сравнения в разделе 13.6: scripts/stage4_eval/results/retrieval/.
В конце печатается, что скопировано и чего не нашлось.
"""
import argparse, json, shutil
from pathlib import Path

QRELS = "split-720-exact-text-v1"
NAMES = {"o1": "опыт 1", "o2": "опыт 2", "ctl": "контроль", "o3": "опыт 3", "o4": "опыт 4", "o5": "опыт 5"}

def classify(m):
    s = (m.get("search_settings") or {}).get("mode") or {}
    if m.get("clip_enabled"): return "o5"
    if s.get("rerank_model"): return "o4" if s.get("candidate_depth", 0) >= 50 else "o3"
    if s.get("query_prefix", "") == "": return "o1"
    return "ctl" if s.get("collection", "").endswith("_e5") else "o2"

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="корень репозитория (по умолчанию текущая папка)")
    ap.add_argument("--out", default="Этапы/Reports/etap4/data_V2", help="куда копировать")
    a = ap.parse_args()
    root, out = Path(a.root).resolve(), Path(a.out)
    if not out.is_absolute():
        out = root / out
    rels, missing, notes = [], [], []

    runs = {}
    for f in sorted((root / "V2/results/retrieval").glob("split*/*/metrics.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            notes.append(f"пропущен {f.relative_to(root).as_posix()}: {e}"); continue
        if m.get("qrels_version") != QRELS or len(m.get("questions", [])) != 720:
            continue
        e = classify(m)
        if e not in runs or m.get("created_at", "") > runs[e][1]:
            runs[e] = (f, m.get("created_at", ""))
    for e, n in NAMES.items():
        if e in runs:
            r = runs[e][0].relative_to(root).as_posix(); rels.append(r); notes.append(f"{n}: {r}")
        else:
            missing.append(f"metrics.json для: {n}")

    gen = root / "V2/results/generation"
    for kind, suffix, files in [("answers", "rerank50", ["answers.jsonl", "run.json"]),
                                ("judge", "rerank50", ["judgments.jsonl", "judge_metrics.json", "run.json"]),
                                ("answers", "refusal", ["answers.jsonl", "run.json"]),
                                ("judge", "refusal", ["judgments.jsonl", "judge_metrics.json", "run.json"])]:
        ds = sorted(d for d in (gen / kind).glob("*_" + suffix) if d.is_dir()) if (gen / kind).is_dir() else []
        if not ds:
            missing.append(f"V2/results/generation/{kind}/*_{suffix}"); continue
        rels += [(ds[-1] / f).relative_to(root).as_posix() for f in files]

    rels += [f"V2/data/rag_eval_questions/{n}" for n in ("eval_questions_split.json", "eval_qrels_split.json", "eval_questions_refusal.json")]
    corpus = sorted(p.relative_to(root).as_posix() for p in (root / "V2/data/chunked_merged_manual").glob("*.chunked.jsonl"))
    rels += corpus or ["V2/data/chunked_merged_manual/*.chunked.jsonl"]
    rels += [f"scripts/stage4_eval/results/retrieval/{n}" for n in (
        "stage4_hitk_results.json", "stage4_hitk_results_e5.json", "stage4_hitk_results_rerank.json", "stage4_hitk_runs.jsonl",
        "stage4_rank_results_base.json", "stage4_rank_results_e5.json", "stage4_rank_results_rerank.json")]

    copied, size = [], 0
    for r in rels:
        src = root / r
        if not src.is_file():
            missing.append(r); continue
        dst = out / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst); copied.append(r); size += src.stat().st_size
    print(f"Папка: {out}")
    print("Выбранные прогоны поиска:")
    for n in notes:
        print("  " + n)
    print(f"Скопировано файлов: {len(copied)} ({size / 1e6:.1f} МБ)")
    groups = {}
    for r in copied:
        d = r.rsplit("/", 1)[0]
        groups[d] = groups.get(d, 0) + 1
    for d, n in sorted(groups.items()):
        print(f"  {d}: {n}")
    print("Не найдено:" if missing else "Не найдено: нет")
    for r in missing:
        print("  " + r)

if __name__ == "__main__":
    main()
