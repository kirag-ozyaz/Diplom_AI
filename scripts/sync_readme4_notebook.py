"""Sync Readme-4 (ver. 2).ipynb markdown from Readme-4.md.

Readme-4.md — master text for Word (sections 1–8 + appendices).
The notebook — working report: synced prose + fixed code cells (not overwritten).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from report_paths import (  # noqa: E402
    README4_MD,
    README4_NB,
    STAGE4_HITK_CHART,
    rel_from_root,
)

MD_PATH = README4_MD
NB_PATH = README4_NB


def md_to_source(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def anchor_section(n: int, body: str) -> str:
    return f'<a id="sec-{n}"></a>\n' + body


def extract_header(md: str) -> str:
    block = md.split("\n---\n", 1)[0].strip()
    if not block.startswith("# "):
        raise SystemExit("Readme-4.md: title block not found")
    return block


def extract_appendices_for_notebook(md: str) -> str:
    m = re.search(r"^## Приложения\b", md, re.MULTILINE)
    if not m:
        raise SystemExit("Readme-4.md: ## Приложения not found")
    body = md[m.start() :].strip()
    body = re.split(r"\n---\n\n\*Отчёт подготовлен", body, maxsplit=1)[0].strip()
    nb_rel = rel_from_root(README4_NB)
    md_rel = rel_from_root(README4_MD)
    body = body.replace(
        f"- Ноутбук этап 4 (ver. 2): `{nb_rel}`\n",
        f"- Исполняемый отчёт: `{nb_rel}` (этот ноутбук)\n"
        f"- Текст для Word: `{md_rel}`\n",
    )
    chart_rel = rel_from_root(STAGE4_HITK_CHART)
    return (
        body
        + f"\n\n*График для сдачи: `{chart_rel}` или вывод ячейки раздела 5.*"
    )


def main() -> None:
    md = MD_PATH.read_text(encoding="utf-8")

    sections: dict[int, str] = {}
    for n in range(1, 9):
        if n < 8:
            pat = rf"^## {n}\. .+?(?=^## {n + 1}\. |\Z)"
        else:
            pat = r"^## 8\. .+?(?=^## Приложения|\Z)"
        m = re.search(pat, md, re.MULTILINE | re.DOTALL)
        if not m:
            raise SystemExit(f"section {n} not found in Readme-4.md")
        sections[n] = m.group(0).strip()

    header = extract_header(md)

    title_cell = (
        header
        + "\n\n**Версия 2 (рабочий документ).** Текст разделов 1–8 синхронизирован с "
        "`Readme-4.md` (мастер для Word). Ниже — оглавление и исполняемые ячейки.\n\n"
        "**Содержание отчёта:**\n"
    )
    toc = [
        (1, "Тема и описание задачи"),
        (2, "База данных"),
        (3, "Параметризация данных"),
        (4, "Архитектура рабочего контура RAG"),
        (5, "Графическое подтверждение (Hit@k)"),
        (6, "Ноутбук или .py файл (прототип)"),
        (7, "Выводы"),
        (8, "План дальнейшей работы"),
    ]
    for n, label in toc:
        title_cell += f"{n}. [{label}](#sec-{n})\n"

    howto = (
        "**Как пользоваться.** (1) Bootstrap. (2) Docker / Milvus. "
        "(3) Раздел 5: **§5.2** прогон → **§5.3** таблица/Plotly (или §5.3 с `force_eval=True`). "
        "(4) Раздел 6 — demo Milvus. (5) **§7** — code-ячейка выводов после §5.2. "
        "Текст: `Readme-4.md` → `python scripts/sync_readme4_notebook.py`."
    )

    sec5 = sections[5]
    idx51 = sec5.find("### 5.1.")
    idx52 = sec5.find("### 5.2.")
    idx53 = sec5.find("### 5.3.")
    sec5_intro = sec5[:idx51].strip() if idx51 >= 0 else sec5
    sec5_51 = sec5[idx51:idx52].strip() if idx51 >= 0 and idx52 > idx51 else ""
    sec5_nb_before_code = (sec5_intro + "\n\n" + sec5_51).strip() if sec5_51 else sec5_intro

    sec5_52_block = sec5[idx52:idx53].strip() if idx52 >= 0 and idx53 > idx52 else ""
    sec5_52_header = (
        '<a id="sec-5-2"></a>\n' + sec5_52_block if sec5_52_block else '<a id="sec-5-2"></a>\n### 5.2. Прогон оценки Hit@k'
    )

    sec5_53_intro = ""
    if idx53 >= 0:
        chunk = sec5[idx53:]
        m_mark = re.search(r"<!-- stage4-eval:5\.3:start -->", chunk)
        if m_mark:
            sec5_53_intro = chunk[: m_mark.start()].strip()
        else:
            sec5_53_intro = re.split(r"<!-- stage4-eval:5\.2:start -->", chunk, maxsplit=1)[0].strip()

    sec5_53_header = (
        '<a id="sec-5-3"></a>\n' + sec5_53_intro
        if sec5_53_intro
        else '<a id="sec-5-3"></a>\n### 5.3. Результаты прогона'
    )

    footer_tail = ""
    if idx53 >= 0:
        m_end = re.search(
            r"<!-- stage4-eval:5\.3:end -->\s*(.*?)(?=\n---\s*$|\Z)",
            sec5[idx53:],
            flags=re.DOTALL,
        )
        if not m_end:
            m_end = re.search(
                r"<!-- stage4-eval:5\.2:end -->\s*(.*?)(?=\n---\s*$|\Z)",
                sec5[idx53:],
                flags=re.DOTALL,
            )
        if m_end:
            footer_tail = m_end.group(1).strip()

    from report_paths import STAGE4_HITK_REPORT_PNG, STAGE4_HITK_RESULTS, md_link

    sec5_after_code = footer_tail or (
        f"Полный JSON: {md_link(STAGE4_HITK_RESULTS)}. "
        f"PNG: {md_link(STAGE4_HITK_CHART)}, {md_link(STAGE4_HITK_REPORT_PNG)}."
    )

    sec6 = sections[6]
    extra_rows = (
        "| `scripts/stage4_eval/demo_stage4_milvus_search.py` | Демо семантического поиска (§6 ноутбука) |\n"
        "| `scripts/test_rag_ollama.py` | Полный RAG (Milvus + Ollama) |\n"
        "| `scripts/sync_readme4_notebook.py` | Обновить текст ячеек ноутбука из `Readme-4.md` |\n"
    )
    sec6_nb = sec6.replace(
        "| Файл | Назначение |\n|------|------------|\n",
        "| Файл | Назначение |\n|------|------------|\n" + extra_rows,
    )

    sec7 = sections[7]
    idx7 = sec7.find("<!-- stage4-eval:7:start -->")
    sec7_nb = sec7[:idx7].strip() if idx7 >= 0 else sec7

    appendices = extract_appendices_for_notebook(md)

    updates = {
        1: anchor_section(1, sections[1]),
        2: anchor_section(2, sections[2]),
        3: anchor_section(3, sections[3]),
        4: anchor_section(4, sections[4]),
        5: anchor_section(5, sec5_nb_before_code),
        6: anchor_section(6, sec6_nb),
        7: anchor_section(7, sec7_nb),
        8: anchor_section(8, sections[8]) + "\n\n" + appendices,
    }

    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    cells = nb["cells"]
    cells[0]["source"] = md_to_source(title_cell)
    cells[1]["source"] = md_to_source(howto)

    sec5_after_assigned = False
    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue
        src = "".join(cell.get("source", []))
        if '<a id="sec-5-2"></a>' in src:
            cell["source"] = md_to_source(sec5_52_header)
            continue
        if '<a id="sec-5-3"></a>' in src:
            cell["source"] = md_to_source(sec5_53_header)
            continue
        for n in range(1, 9):
            if f'<a id="sec-{n}"></a>' in src:
                cell["source"] = md_to_source(updates[n])
                break
        else:
            if (
                not sec5_after_assigned
                and "stage4_hitk_chart" in src
                and '<a id="sec-5"></a>' not in src
                and '<a id="sec-5-3"></a>' not in src
            ):
                cell["source"] = md_to_source(sec5_after_code)
                sec5_after_assigned = True

    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Updated: {NB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
