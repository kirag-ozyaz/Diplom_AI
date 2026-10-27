# -*- coding: utf-8 -*-
"""
Метрики ранжирования для этапа 4 (бинарная релевантность): Hit@k, MRR, MRR@k, nDCG@k.

rank — позиция (1-based) первого релевантного результата, None = не найден в top-k_max.

CLI:
  python rank_metrics.py R1.json [R2.json ...] [--out-dir DIR]        # сравнение rank-результатов
  python rank_metrics.py --from-hitk H1.json [H2.json ...] [--out-dir DIR]  # ГРАНИЦЫ по hit@1/3/5
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable, Optional, Sequence

DEFAULT_KS = (1, 3, 5, 10)


# ---------- чистые функции ----------
def reciprocal_rank(rank: Optional[int], k: Optional[int] = None) -> float:
    if rank is None or rank < 1 or (k is not None and rank > k):
        return 0.0
    return 1.0 / rank


def dcg_at_k(rels: Sequence[float], k: int) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]))


def ndcg_at_k(rels: Sequence[float], k: int, n_relevant: Optional[int] = None) -> float:
    """rels — вектор релевантности по позициям выдачи; n_relevant — общее число релевантных (для IDCG)."""
    n_rel = n_relevant if n_relevant is not None else int(sum(1 for r in rels if r > 0))
    if n_rel <= 0:
        return 0.0
    idcg = dcg_at_k([1.0] * n_rel, k)
    return dcg_at_k(rels, k) / idcg if idcg > 0 else 0.0


def ndcg_from_rank(rank: Optional[int], k: int) -> float:
    """Один релевантный документ: nDCG@k = 1/log2(rank+1), если rank<=k."""
    if rank is None or rank < 1 or rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def hit_at_k(rank: Optional[int], k: int) -> float:
    return 1.0 if rank is not None and 1 <= rank <= k else 0.0


def summarize_ranks(ranks: Iterable[Optional[int]], ks: Sequence[int] = DEFAULT_KS,
                    k_max: Optional[int] = None) -> dict:
    ranks = list(ranks)
    n = len(ranks)
    if n == 0:
        return {"n": 0}
    out: dict = {"n": n}
    for k in ks:
        out[f"hit@{k}"] = sum(hit_at_k(r, k) for r in ranks) / n
    out["mrr"] = sum(reciprocal_rank(r, k_max) for r in ranks) / n
    for k in ks:
        out[f"mrr@{k}"] = sum(reciprocal_rank(r, k) for r in ranks) / n
    for k in ks:
        out[f"ndcg@{k}"] = sum(ndcg_from_rank(r, k) for r in ranks) / n
    return out


def summarize_rel_lists(rel_lists: Sequence[Sequence[int]], n_relevant: Sequence[int],
                        ks: Sequence[int] = DEFAULT_KS) -> dict:
    """Для случая нескольких expected_clause: nDCG по полному вектору релевантности."""
    n = len(rel_lists)
    return {f"ndcg@{k}": sum(ndcg_at_k(r, k, m) for r, m in zip(rel_lists, n_relevant)) / n for k in ks} if n else {}


# ---------- границы по hit@1/3/5 ----------
def bounds_from_hits(details: Sequence[dict], ks: Sequence[int] = DEFAULT_KS) -> dict:
    """
    Известно только, в какую корзину попал rank: 1, 2-3, 4-5, >5.
    Нижняя граница: rank = худший в корзине (3, 5, не найден).
    Верхняя: rank = лучший в корзине (2, 4; для >5 — 6, т.е. найден на позиции 6).
    """
    lo, hi = [], []
    for d in details:
        h = d.get("hit", {})
        if h.get("@1"):
            lo.append(1); hi.append(1)
        elif h.get("@3"):
            lo.append(3); hi.append(2)
        elif h.get("@5"):
            lo.append(5); hi.append(4)
        else:
            lo.append(None); hi.append(6)
    lo_s, hi_s = summarize_ranks(lo, ks), summarize_ranks(hi, ks)
    res = {"n": len(details)}
    for key in lo_s:
        if key == "n":
            continue
        res[key] = (lo_s[key], hi_s[key])
    return res


# ---------- CLI ----------
LABELS = {"base": "Опыт 1 base", "e5": "Опыт 2 E5 prefixes", "rerank": "Опыт 3 E5+rerank"}


def guess_label(path: Path) -> str:
    s = path.stem
    for key in ("rerank", "e5"):
        if s.endswith("_" + key):
            return LABELS[key]
    return LABELS["base"]


def _fmt(v) -> str:
    if isinstance(v, tuple):
        return f"{v[0]:.3f}–{v[1]:.3f}"
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def write_table(rows: list[tuple[str, dict]], cols: list[str], out_dir: Path, stem: str, title: str) -> str:
    header = ["Эксперимент", "N"] + cols
    md = [f"### {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for label, m in rows:
        md.append("| " + " | ".join([label, str(m["n"])] + [_fmt(m.get(c, "")) for c in cols]) + " |")
    text = "\n".join(md) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.md").write_text(text, encoding="utf-8")
    with open(out_dir / f"{stem}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if rows and isinstance(rows[0][1].get(cols[0]), tuple):
            w.writerow(["experiment", "n"] + [f"{c}_{b}" for c in cols for b in ("low", "high")])
            for label, m in rows:
                w.writerow([label, m["n"]] + [round(x, 4) for c in cols for x in m[c]])
        else:
            w.writerow(["experiment", "n"] + cols)
            for label, m in rows:
                w.writerow([label, m["n"]] + [round(m[c], 4) for c in cols])
    return text


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--from-hitk", action="store_true", help="входные файлы — stage4_hitk_results*.json; выводятся ГРАНИЦЫ")
    ap.add_argument("--ks", default="1,3,5,10")
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    ap.add_argument("--labels", default=None, help="подписи через запятую (по умолчанию из имени файла)")
    a = ap.parse_args(argv)
    ks = tuple(int(x) for x in a.ks.split(","))
    labels = a.labels.split(",") if a.labels else [guess_label(p) for p in a.files]
    rows = []
    for p, lab in zip(a.files, labels):
        data = json.loads(p.read_text(encoding="utf-8"))
        if a.from_hitk:
            rows.append((lab, bounds_from_hits(data["details"], ks)))
        else:
            ranks = [d.get("rank") for d in data["details"]]
            rows.append((lab, summarize_ranks(ranks, ks, data.get("k_max"))))
    if a.from_hitk:
        cols = ["hit@1", "hit@3", "hit@5", "mrr@5", "mrr"] + [f"ndcg@{k}" for k in ks]
        title = "ГРАНИЦЫ (нижняя–верхняя) MRR/nDCG, оценённые по hit@1/3/5 — НЕ точные значения"
        stem = "rank_metrics_bounds_from_hitk"
    else:
        cols = [f"hit@{k}" for k in ks] + ["mrr"] + [f"mrr@{k}" for k in ks] + [f"ndcg@{k}" for k in ks]
        title = "Сравнение экспериментов: Hit@k, MRR, nDCG@k"
        stem = "rank_metrics_comparison"
    print(write_table(rows, cols, a.out_dir, stem, title))
    print(f"Сохранено: {a.out_dir / (stem + '.md')}, {a.out_dir / (stem + '.csv')}")


if __name__ == "__main__":
    main()
