# -*- coding: utf-8 -*-
"""Баннеры и логи этапа 4 (консоль + файл STAGE4_RUN_LOG)."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

_BANNER_WIDTH = 60


def run_log_path() -> Path | None:
    raw = (os.environ.get("STAGE4_RUN_LOG") or "").strip()
    return Path(raw) if raw else None


def progress_line(message: str) -> None:
    """Строка прогресса по вопросу: консоль; в файл — если нет tee родителя."""
    print(message, flush=True)
    if os.environ.get("STAGE4_LOG_TEE") == "1":
        return
    path = run_log_path()
    if path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
        except OSError:
            pass


def log_line(message: str) -> None:
    """Строка с временем в консоль и в общий лог-файл прогона."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {message}"
    print(line, flush=True)
    if os.environ.get("STAGE4_LOG_TEE") == "1":
        return
    path = run_log_path()
    if path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def log_run_start(script: str, **meta: object) -> None:
    log_line(f"Запуск {script} (pid={os.getpid()})")
    log_path = run_log_path()
    if log_path:
        log_line(f"  лог-файл: {log_path}")
    log_line(f"  Python: {sys.executable}")
    for key, value in meta.items():
        if value is not None and value != "":
            log_line(f"  {key}: {value}")


def log_run_end(script: str, *, ok: bool = True, note: str = "") -> None:
    status = "OK" if ok else "ОШИБКА"
    msg = f"Завершение {script}: {status}"
    if note:
        msg += f" — {note}"
    log_line(msg)


def banner_step() -> str:
    """Префикс шага из STAGE4_BANNER_STEP (задаёт run_all.ps1) или пустая строка."""
    return (os.environ.get("STAGE4_BANNER_STEP") or "").strip()


def stage_banner(title: str, *, detail: str = "", step: str | None = None) -> None:
    """Печать блока === как в eval_rag_performance / LLM-judge."""
    prefix = (step if step is not None else banner_step()).strip()
    head = f"{prefix} {title}".strip() if prefix else title
    log_line("=" * _BANNER_WIDTH)
    log_line(head)
    log_line("=" * _BANNER_WIDTH)
    if detail:
        line = detail if detail.startswith("Этап:") else f"Этап: {detail}"
        log_line(f"[*] {line}")


def opening_stage_banner(title: str, *, detail: str = "", step: str | None = None) -> None:
    """Баннер в начале скрипта. Из run_*.ps1 он уже напечатан, второй раз не пишем."""
    if os.environ.get("STAGE4_LOG_TEE") == "1":
        return
    stage_banner(title, detail=detail, step=step)
