# -*- coding: utf-8 -*-
"""
Чтение и запись реестра контрольных вопросов этапа 4.

Формат реестра (JSON-объект):
  title, source_file, n_questions, questions[] —
  в каждой записи: id, registry_id, query, expected_clause, section.

Поддерживается прежний формат — плоский массив вопросов (при чтении преобразуется).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    q = (row.get("query") or row.get("question") or "").strip()
    rid = row.get("registry_id")
    num = row.get("id")
    if not rid and num is not None:
        rid = f"Q-{int(num):03d}"
    return {
        "id": num,
        "registry_id": rid,
        "query": q,
        "expected_clause": str(row.get("expected_clause") or "").strip(),
        "section": (row.get("section") or "").strip(),
    }


def load_eval_questions(path: Path) -> list[dict[str, Any]]:
    """Список вопросов для Hit@k / generation (поля id, query, expected_clause, …)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict) and isinstance(data.get("questions"), list):
        rows = data["questions"]
    else:
        raise ValueError(f"Неизвестный формат вопросов: {path}")
    return [_normalize_row(r) for r in rows]


def load_eval_registry(path: Path) -> dict[str, Any]:
    """Полный реестр; legacy-массив оборачивается в объект."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return wrap_questions(
            [_normalize_row(r) for r in data],
            title=path.stem,
            source_file=str(path.name),
        )
    if isinstance(data, dict) and "questions" in data:
        reg = dict(data)
        reg["questions"] = [_normalize_row(r) for r in reg["questions"]]
        reg["n_questions"] = len(reg["questions"])
        return reg
    raise ValueError(f"Неизвестный формат вопросов: {path}")


def wrap_questions(
    questions: list[dict[str, Any]],
    *,
    title: str,
    source_file: str,
) -> dict[str, Any]:
    qs = [_normalize_row(q) for q in questions]
    for i, q in enumerate(qs, start=1):
        if q.get("id") is None:
            q["id"] = i
        if not q.get("registry_id"):
            q["registry_id"] = f"Q-{int(q['id']):03d}"
    return {
        "title": title,
        "source_file": source_file,
        "n_questions": len(qs),
        "questions": qs,
    }


def write_eval_registry(path: Path, registry: dict[str, Any]) -> None:
    if "questions" not in registry:
        raise ValueError("registry must contain 'questions'")
    reg = wrap_questions(
        registry["questions"],
        title=str(registry.get("title") or path.stem),
        source_file=str(registry.get("source_file") or path.name),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_eval_registry_from_path(
    path: Path,
    *,
    title: str,
    source_file: str,
    questions: list[dict[str, Any]],
) -> None:
    write_eval_registry(
        path,
        wrap_questions(questions, title=title, source_file=source_file),
    )
