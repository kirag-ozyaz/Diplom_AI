# -*- coding: utf-8 -*-
"""Графики Hit@k для отчёта этапа 4.

- PNG (matplotlib): Word, Readme-4.md, eval_retrieval_hitk.py
- Plotly (ноутбук): интерактивные графики в output ячейки
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def configure_matplotlib() -> None:
    """Шрифт с кириллицей (Windows / Linux)."""
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    plt.rcParams["axes.unicode_minus"] = False
    for name in ("Segoe UI", "Arial", "DejaVu Sans"):
        try:
            if any(getattr(f, "name", "") == name for f in font_manager.fontManager.ttflist):
                plt.rcParams["font.family"] = name
                return
        except Exception:
            continue


def plot_hitk_bar_chart(
    results: dict[str, Any],
    chart_path: Path,
    *,
    show: bool = False,
    dpi: int = 150,
) -> Path:
    """Классическая столбчатая диаграмма Hit@1 / Hit@3 / Hit@5 (matplotlib)."""
    import matplotlib.pyplot as plt

    configure_matplotlib()
    plt.rcParams.update({"figure.dpi": dpi, "savefig.dpi": dpi, "font.size": 11})

    metrics = results["metrics_percent"]
    n_q = results.get("n_questions", len(results.get("details") or []))
    model = results.get("text_model", "—")
    collection = results.get("collection", "—")

    labels = ["Hit@1", "Hit@3", "Hit@5"]
    values = [float(metrics["hit@1"]), float(metrics["hit@3"]), float(metrics["hit@5"])]
    colors = ["#2E86AB", "#28A745", "#E67E22"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="#333333", linewidth=0.8, width=0.5)
    ax.set_ylim(0, max(100, max(values) + 15) if values else 100)
    ax.set_ylabel("Доля успешных запросов, %")
    ax.set_title("Метрики retrieval по ПУЭ (этап 4)")
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)

    for bar, v in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 1.5,
            f"{v:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    fig.text(
        0.99,
        0.02,
        f"n = {n_q}  |  {collection}  |  {model}",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout()

    chart_path = Path(chart_path)
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chart_path, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(fig)
    return chart_path


def plot_hitk_report(
    results: dict[str, Any],
    chart_path: Path,
    *,
    show: bool = False,
    dpi: int = 150,
) -> Path:
    """Детализация без повтора столбцов: heatmap успехов + cosine top-1."""
    import matplotlib.pyplot as plt
    import numpy as np

    configure_matplotlib()
    plt.rcParams.update(
        {
            "figure.dpi": dpi,
            "savefig.dpi": dpi,
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
        }
    )

    metrics = results["metrics_percent"]
    details = results.get("details") or []
    n_q = results.get("n_questions", len(details))
    model = results.get("text_model", "—")
    collection = results.get("collection", "—")

    k_labels = ["Hit@1", "Hit@3", "Hit@5"]
    h1, h3, h5 = (float(metrics["hit@1"]), float(metrics["hit@3"]), float(metrics["hit@5"]))

    fig, (ax2, ax3) = plt.subplots(1, 2, figsize=(11, 5.5))

    if details:
        ids = [str(d.get("id", i + 1)) for i, d in enumerate(details)]
        hit_mat = np.array(
            [
                [
                    1 if d.get("hit", {}).get("@1") else 0,
                    1 if d.get("hit", {}).get("@3") else 0,
                    1 if d.get("hit", {}).get("@5") else 0,
                ]
                for d in details
            ],
            dtype=float,
        )
        im = ax2.imshow(hit_mat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        ax2.set_xticks([0, 1, 2])
        ax2.set_xticklabels(k_labels)
        ax2.set_yticks(range(len(ids)))
        ax2.set_yticklabels(ids, fontsize=9)
        ax2.set_xlabel("Метрика")
        ax2.set_ylabel("ID вопроса")
        ax2.set_title("Успех по каждому запросу")
        cbar = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
        cbar.set_ticks([0, 1])
        cbar.set_ticklabels(["нет", "да"])
    else:
        ax2.text(0.5, 0.5, "Нет details в JSON", ha="center", va="center")
        ax2.set_axis_off()

    if details:
        ids_num = [d.get("id", i + 1) for i, d in enumerate(details)]
        scores = [d.get("top1_score") or 0.0 for d in details]
        x = np.arange(len(ids_num))
        ax3.bar(x, scores, color="#5C6BC0", edgecolor="#333333", linewidth=0.5)
        ax3.set_xticks(x)
        ax3.set_xticklabels([str(i) for i in ids_num], fontsize=8)
        ax3.set_xlabel("ID вопроса")
        ax3.set_ylabel("Cosine score (1-й результат)")
        ax3.set_title("Уверенность поиска (top-1)")
        ax3.set_ylim(0, 1.0)
        ax3.yaxis.grid(True, linestyle="--", alpha=0.45)
        ax3.set_axisbelow(True)
    else:
        ax3.set_axis_off()

    fig.suptitle(
        f"Этап 4 — детализация retrieval  |  "
        f"Hit@1 {h1:.1f}%  Hit@3 {h3:.1f}%  Hit@5 {h5:.1f}%  |  n={n_q}",
        fontsize=11,
        y=1.02,
    )
    fig.text(
        0.99,
        0.01,
        f"{collection}  |  {model}",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout()

    chart_path = Path(chart_path)
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chart_path, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(fig)
    return chart_path


def plot_from_json(json_path: Path, chart_path: Path, *, show: bool = False) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return plot_hitk_report(data, chart_path, show=show)


def show_plotly(fig) -> bool:
    """Интерактивный Plotly в ноутбуке. True, если что-то отобразилось."""
    import plotly.io as pio

    try:
        from IPython import get_ipython

        if get_ipython() is not None:
            for name in ("vscode", "notebook_connected", "iframe", "notebook"):
                if name in pio.renderers:
                    try:
                        fig.show(renderer=name)
                        return True
                    except Exception:
                        continue
    except ImportError:
        pass

    try:
        from IPython.display import HTML, display
    except ImportError:
        fig.show(renderer=pio.renderers.default or "browser")
        return True

    for plotlyjs in ("inline", "cdn"):
        try:
            display(HTML(fig.to_html(include_plotlyjs=plotlyjs, full_html=False)))
            return True
        except Exception:
            continue
    return False


def plot_hitk_bar_chart_plotly(results: dict[str, Any]):
    """Интерактивные столбцы Hit@k (Plotly, только ноутбук)."""
    import plotly.graph_objects as go

    metrics = results["metrics_percent"]
    n_q = results.get("n_questions", len(results.get("details") or []))
    model = results.get("text_model", "—")
    collection = results.get("collection", "—")
    labels = ["Hit@1", "Hit@3", "Hit@5"]
    values = [float(metrics["hit@1"]), float(metrics["hit@3"]), float(metrics["hit@5"])]

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=["#2E86AB", "#28A745", "#E67E22"],
                text=[f"{v:.1f}%" for v in values],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=f"Метрики retrieval по ПУЭ (этап 4)<br><sup>n={n_q} | {collection} | {model}</sup>",
        yaxis_title="Доля успешных запросов, %",
        yaxis_range=[0, max(100, max(values) + 15) if values else 100],
        template="plotly_white",
        height=450,
    )
    return fig


def plot_hitk_report_plotly(results: dict[str, Any]):
    """Интерактивная детализация: heatmap + cosine (Plotly)."""
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    metrics = results["metrics_percent"]
    details = results.get("details") or []
    n_q = results.get("n_questions", len(details))
    model = results.get("text_model", "—")
    collection = results.get("collection", "—")
    h1, h3, h5 = (float(metrics["hit@1"]), float(metrics["hit@3"]), float(metrics["hit@5"]))
    k_labels = ["Hit@1", "Hit@3", "Hit@5"]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Успех по каждому запросу", "Уверенность поиска (top-1)"),
        horizontal_spacing=0.12,
    )

    if details:
        ids = [str(d.get("id", i + 1)) for i, d in enumerate(details)]
        z = [
            [
                1 if d.get("hit", {}).get("@1") else 0,
                1 if d.get("hit", {}).get("@3") else 0,
                1 if d.get("hit", {}).get("@5") else 0,
            ]
            for d in details
        ]
        fig.add_trace(
            go.Heatmap(
                z=z,
                x=k_labels,
                y=ids,
                colorscale=[[0, "#d73027"], [0.5, "#ffffbf"], [1, "#1a9850"]],
                showscale=True,
                colorbar=dict(title=""),
                hovertemplate="ID %{y}<br>%{x}: %{z}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        ids_num = [d.get("id", i + 1) for i, d in enumerate(details)]
        scores = [float(d.get("top1_score") or 0.0) for d in details]
        fig.add_trace(
            go.Bar(
                x=[str(i) for i in ids_num],
                y=scores,
                marker_color="#5C6BC0",
                hovertemplate="ID %{x}<br>score=%{y:.3f}<extra></extra>",
            ),
            row=1,
            col=2,
        )
        fig.update_yaxes(title_text="Cosine score", range=[0, 1], row=1, col=2)

    fig.update_layout(
        title=(
            f"Этап 4 — детализация retrieval | "
            f"Hit@1 {h1:.1f}% Hit@3 {h3:.1f}% Hit@5 {h5:.1f}% | n={n_q}<br>"
            f"<sup>{collection} | {model}</sup>"
        ),
        template="plotly_white",
        height=520,
        showlegend=False,
    )
    fig.update_xaxes(title_text="Метрика", row=1, col=1)
    fig.update_yaxes(title_text="ID вопроса", row=1, col=1)
    fig.update_xaxes(title_text="ID вопроса", row=1, col=2)
    return fig


def save_hitk_png_for_word(
    results: dict[str, Any],
    chart_path: Path,
    report_path: Path,
    *,
    dpi: int = 150,
) -> tuple[Path, Path]:
    """Статичные PNG для Word / md (без show)."""
    plot_hitk_bar_chart(results, chart_path, show=False, dpi=dpi)
    plot_hitk_report(results, report_path, show=False, dpi=dpi)
    return chart_path, report_path


__all__ = [
    "configure_matplotlib",
    "plot_hitk_bar_chart",
    "plot_hitk_report",
    "plot_hitk_bar_chart_plotly",
    "plot_hitk_report_plotly",
    "show_plotly",
    "save_hitk_png_for_word",
    "plot_from_json",
]
