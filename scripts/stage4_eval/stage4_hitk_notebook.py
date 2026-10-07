# -*- coding: utf-8 -*-
"""§5.2 / §5.3 ноутбука Readme-4: прогон Hit@k и отображение результатов."""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_SESSION_KEY = "STAGE4_HITK_RESULTS"


def _user_ns() -> dict:
    try:
        from IPython import get_ipython

        ip = get_ipython()
        if ip is not None:
            return ip.user_ns
    except ImportError:
        pass
    return globals()


def _load_eval_module(stage4_dir: Path):
    name = "eval_retrieval_hitk"
    path = stage4_dir / "eval_retrieval_hitk.py"
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def run_eval(reports: Path, root: Path, *, refresh_readme: bool = True) -> dict[str, Any]:
    scripts = root / "scripts"
    stage4 = scripts / "stage4_eval"
    for p in (scripts, stage4):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    eval_mod = _load_eval_module(stage4)
    results = eval_mod.run_hitk_eval(refresh_readme=refresh_readme)
    _user_ns()[_SESSION_KEY] = results
    return results


def load_results_json(results_path: Path) -> dict[str, Any]:
    return json.loads(results_path.read_text(encoding="utf-8"))


def ensure_results(
    reports: Path,
    root: Path,
    results_path: Path,
    *,
    refresh_readme: bool = True,
    force_eval: bool = False,
) -> dict[str, Any]:
    """Прогон при необходимости; итог всегда из JSON на диске."""
    ns = _user_ns()
    if force_eval:
        run_eval(reports, root, refresh_readme=refresh_readme)
    elif _SESSION_KEY not in ns and not results_path.is_file():
        print("Нет JSON — выполняю прогон Hit@k (§5.2)...")
        run_eval(reports, root, refresh_readme=refresh_readme)
    elif _SESSION_KEY not in ns and results_path.is_file():
        print(
            "Прогон в этой сессии не выполнялся — показ данных с диска. "
            "Для нового прогона: ячейка §5.2 или force_eval=True здесь."
        )

    if not results_path.is_file():
        raise FileNotFoundError(
            f"Нет {results_path.name}. Запустите ячейку §5.2 (Milvus должен быть доступен)."
        )
    results = load_results_json(results_path)
    ns[_SESSION_KEY] = results
    return results


def render_section_53(
    results: dict[str, Any],
    reports: Path,
    root: Path,
    *,
    results_path: Path | None = None,
) -> None:
    from IPython.display import Markdown, display

    scripts = root / "scripts"
    stage4 = scripts / "stage4_eval"
    for p in (scripts, stage4):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    from report_paths import (
        STAGE4_HITK_CHART,
        STAGE4_HITK_REPORT_PNG,
        STAGE4_HITK_RESULTS,
    )

    results_path = results_path or STAGE4_HITK_RESULTS
    chart_path = STAGE4_HITK_CHART
    report_path = STAGE4_HITK_REPORT_PNG

    report_name = "stage4_hitk_report"
    if report_name in sys.modules:
        report_mod = importlib.reload(sys.modules[report_name])
    else:
        spec_r = importlib.util.spec_from_file_location(
            report_name, stage4 / "stage4_hitk_report.py"
        )
        report_mod = importlib.util.module_from_spec(spec_r)
        sys.modules[report_name] = report_mod
        assert spec_r.loader is not None
        spec_r.loader.exec_module(report_mod)

    evaluated = results.get("evaluated_at", "—")
    print(f"§5.3 — данные прогона: {evaluated}")

    display(
        Markdown(
            "### 5.3. Результаты прогона\n\n"
            + report_mod.build_section_52_markdown(
                results,
                results_path=results_path,
                max_hit5_examples=None,
            )
        )
    )

    plot_name = "plot_stage4_hitk"
    if plot_name in sys.modules:
        plot_mod = importlib.reload(sys.modules[plot_name])
    else:
        spec = importlib.util.spec_from_file_location(plot_name, stage4 / "plot_stage4_hitk.py")
        plot_mod = importlib.util.module_from_spec(spec)
        sys.modules[plot_name] = plot_mod
        assert spec.loader is not None
        spec.loader.exec_module(plot_mod)

    ok_bar = plot_mod.show_plotly(plot_mod.plot_hitk_bar_chart_plotly(results))
    ok_rep = plot_mod.show_plotly(plot_mod.plot_hitk_report_plotly(results))
    plot_mod.save_hitk_png_for_word(results, chart_path, report_path, dpi=150)
    print(f"PNG для Word/md: {chart_path}")
    print(f"PNG для Word/md: {report_path}")

    from IPython.display import Image, display

    if not (ok_bar and ok_rep):
        print(
            "Plotly в этой IDE не отобразился — ниже превью PNG "
            "(те же файлы, что для Word)."
        )
    print("Превью графиков (matplotlib):")
    display(Image(filename=str(chart_path)))
    display(Image(filename=str(report_path)))
