"""Сборка папки data_V1 для ноутбука Etap4_V1.ipynb (этап 4, первая версия).

Запуск из корня репозитория Diplom_AI:
    python scripts/stage4_eval/collect_data_V1_zip.py
    python scripts/stage4_eval/collect_data_V1_zip.py --out D:/tmp/data_V1
    python scripts/stage4_eval/collect_data_V1_zip.py --no-zip      # только папка, без архива

Скрипт только копирует файлы (исходные файлы не меняются) и в конце печатает,
что скопировано и чего не нашлось. Структура путей внутри data_V1 повторяет репозиторий.

После копирования рядом с папкой создаётся архив data_V1.zip (внутри папка data_V1),
который выкладывается на Drive и скачивается первой ячейкой ноутбука. Если архив
с таким именем уже есть, он не перезаписывается: создаётся data_V1_2.zip и т. д.
(перезаписать можно ключом --force).
"""
import argparse, zipfile, shutil
from pathlib import Path

FILES = [
    "config/rag_runtime.json",
    "src/preprocessing/Create_embeddings/E5/rag_runtime_e5.json",
    "src/preprocessing/Create_embeddings/Rerank/rag_runtime_rerank.json",
    "data/corpus_inventory.json",
    *[f"scripts/stage4_eval/results/retrieval/{n}" for n in (
        "stage4_hitk_results.json", "stage4_hitk_results_e5.json", "stage4_hitk_results_rerank.json", "stage4_hitk_runs.jsonl",
        "stage4_rank_results_base.json", "stage4_rank_results_e5.json", "stage4_rank_results_rerank.json")],
    *[f"scripts/stage4_eval/results/generation/stage4_{k}{s}.json"
      for k in ("gen_eval_results", "llm_judge_metrics", "performance_metrics") for s in ("", "_e5", "_rerank")],
]
GLOBS = [
    "data/rag_eval_questions/eval_questions*.json",   # все версии набора вопросов (серия прогонов опыта 1)
    "data/chunked/*.chunked.jsonl",                   # корпус V1
    "data/chunked/image_*/*",                         # изображения корпуса V1
]

def make_zip(out, force=False):
    """Упаковывает папку out в ZIP рядом с ней; внутри архива верхняя папка с тем же именем."""
    z = out.with_suffix(".zip")
    if z.exists() and not force:
        i = 2
        while out.with_name(f"{out.name}_{i}.zip").exists():
            i += 1
        z = out.with_name(f"{out.name}_{i}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out.parent).as_posix())
    print(f"Архив: {z} ({z.stat().st_size / 1e6:.1f} МБ)")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="корень репозитория (по умолчанию текущая папка)")
    ap.add_argument("--out", default="Этапы/Reports/etap4/data_V1", help="куда копировать")
    ap.add_argument("--no-zip", action="store_true", help="не создавать ZIP")
    ap.add_argument("--force", action="store_true", help="перезаписать существующий ZIP")
    a = ap.parse_args()
    root, out = Path(a.root).resolve(), Path(a.out)
    if not out.is_absolute():
        out = root / out
    rels = list(FILES)
    for g in GLOBS:
        found = sorted(p.relative_to(root).as_posix() for p in root.glob(g) if p.is_file())
        rels += found or [g]
    copied, missing, size = [], [], 0
    for r in rels:
        src = root / r
        if not src.is_file():
            missing.append(r); continue
        dst = out / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst); copied.append(r); size += src.stat().st_size
    print(f"Папка: {out}")
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
    if not a.no_zip:
        make_zip(out, a.force)

if __name__ == "__main__":
    main()
