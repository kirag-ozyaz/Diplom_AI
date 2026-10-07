# -*- coding: utf-8 -*-
"""
Снять логи контейнеров Milvus в infra/milvus/logs/<дата-время>/.

Из корня репозитория:
  python scripts/start_milvus_logs.py
  python scripts/start_milvus_logs.py --since 6h
  python scripts/start_milvus_logs.py --tail 500
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from notebook_bootstrap import find_project_root

MILVUS_CONTAINERS = (
    "milvus-standalone",
    "milvus-etcd",
    "milvus-minio",
)

INSPECT_FORMAT = (
    "{{.Name}}\tstatus={{.State.Status}}\t"
    "exit={{.State.ExitCode}}\toom={{.State.OOMKilled}}\t"
    "finished={{.State.FinishedAt}}"
)


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _write(path: Path, stdout: str, stderr: str, exit_code: int) -> None:
    parts: list[str] = []
    if stdout:
        parts.append(stdout.rstrip("\n"))
    if stderr:
        parts.append("--- stderr ---")
        parts.append(stderr.rstrip("\n"))
    if exit_code != 0 and not parts:
        parts.append(f"команда завершилась с кодом {exit_code}")
    path.write_text("\n".join(parts) + ("\n" if parts else ""), encoding="utf-8")


def collect_milvus_logs(
    *,
    root: Path | None = None,
    since: str = "2h",
    tail: int | None = None,
    output_parent: Path | None = None,
) -> int:
    project_root = find_project_root(root)
    milvus_dir = project_root / "infra" / "milvus"
    compose_file = milvus_dir / "docker-compose.yml"
    if not compose_file.is_file():
        print(f"Не найден файл: {compose_file}", file=sys.stderr)
        return 1

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = output_parent if output_parent is not None else milvus_dir / "logs"
    out_dir = base / stamp
    out_dir.mkdir(parents=True, exist_ok=False)

    ps = _run(["docker", "compose", "ps", "-a"], cwd=milvus_dir)
    _write(out_dir / "compose-ps.txt", ps.stdout, ps.stderr, ps.returncode)

    for name in MILVUS_CONTAINERS:
        cmd = ["docker", "logs", name, "--timestamps"]
        if tail is not None:
            cmd.extend(["--tail", str(tail)])
        else:
            cmd.extend(["--since", since])
        result = _run(cmd)
        _write(out_dir / f"{name}.log", result.stdout, result.stderr, result.returncode)

    inspect_lines: list[str] = []
    for name in MILVUS_CONTAINERS:
        ins = _run(["docker", "inspect", name, "--format", INSPECT_FORMAT])
        line = (ins.stdout or ins.stderr or "").strip()
        if not line and ins.returncode != 0:
            line = f"{name}\tinspect failed (code {ins.returncode})"
        inspect_lines.append(line)
    (out_dir / "inspect-state.txt").write_text(
        "\n".join(inspect_lines) + "\n",
        encoding="utf-8",
    )

    readme = (
        f"Снимок логов Milvus: {stamp}\n"
        f"Каталог compose: {milvus_dir}\n"
        f"Параметры: since={since!r}, tail={tail!r}\n"
        f"\nФайлы:\n"
        f"  compose-ps.txt — docker compose ps -a\n"
        f"  milvus-*.log — docker logs --timestamps\n"
        f"  inspect-state.txt — OOMKilled, exit code, статус\n"
    )
    (out_dir / "README.txt").write_text(readme, encoding="utf-8")

    print(f"Логи сохранены: {out_dir}")
    if ps.returncode != 0:
        print(
            "Предупреждение: docker compose ps завершился с ошибкой (Docker запущен?).",
            file=sys.stderr,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Экспорт логов Milvus (standalone, etcd, minio) в infra/milvus/logs/.",
    )
    parser.add_argument("--since", default="2h", help="Окно docker logs (по умолчанию 2h).")
    parser.add_argument("--tail", type=int, default=None, metavar="N", help="Последние N строк.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Родительская папка вместо infra/milvus/logs.",
    )
    args = parser.parse_args()
    return collect_milvus_logs(
        since=args.since,
        tail=args.tail,
        output_parent=args.output_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())