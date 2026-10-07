# -*- coding: utf-8 -*-
"""
Проверка CUDA / GPU для проекта: эмбеддинги (PyTorch) и Ollama (Docker).
Запуск из корня: python scripts/compute_detect.py [--json]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
EMBED_DIR = ROOT / "src" / "preprocessing" / "Create_embeddings"
OLLAMA_DIR = ROOT / "infra" / "docker" / "Dockerfile.ollama"


@dataclass
class ComputeReport:
    nvidia_smi: bool
    gpu_name: Optional[str]
    vram_gb: Optional[float]
    torch_cuda: bool
    torch_cuda_device: Optional[str]
    docker_available: bool
    docker_nvidia_runtime: bool
    embedding_device_recommended: str
    ollama_compose_mode: str
    ollama_compose_files: list[str]
    ollama_model_recommended: str
    ollama_model_reason: str
    notes: list[str]


def _run(cmd: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def detect_nvidia_smi() -> tuple[bool, Optional[str], Optional[float]]:
    if not shutil.which("nvidia-smi"):
        return False, None, None
    proc = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return False, None, None
    line = proc.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    name = parts[0] if parts else None
    vram: Optional[float] = None
    if len(parts) > 1:
        try:
            vram = round(float(parts[1]) / 1024.0, 2)
        except ValueError:
            pass
    return True, name, vram


def _pip_cuda_index_hint(gpu_name: Optional[str]) -> str:
    """Индекс PyTorch: cu128 для RTX 50xx и новее, иначе cu124."""
    name = (gpu_name or "").lower()
    if any(x in name for x in ("5060", "5070", "5080", "5090", "50 ", "blackwell")):
        return "cu128"
    return "cu124"


def detect_torch_cuda() -> tuple[bool, Optional[str]]:
    try:
        import torch
    except (ImportError, OSError, PermissionError):
        return False, None
    if not torch.cuda.is_available():
        return False, None
    try:
        return True, torch.cuda.get_device_name(0)
    except Exception:
        return True, "cuda:0"


def detect_docker() -> tuple[bool, bool]:
    if not shutil.which("docker"):
        return False, False
    proc = _run(["docker", "info"])
    if proc.returncode != 0:
        return True, False
    blob = (proc.stdout + proc.stderr).lower()
    nvidia_runtime = "nvidia" in blob and ("run" in blob or "runtime" in blob or "default runtime" in blob)
    return True, nvidia_runtime


def build_compute_report() -> ComputeReport:
    notes: list[str] = []
    smi_ok, gpu_name, vram = detect_nvidia_smi()
    torch_ok, torch_dev = detect_torch_cuda()
    docker_ok, docker_nvidia = detect_docker()

    if smi_ok and not torch_ok:
        pip_hint = _pip_cuda_index_hint(gpu_name)
        notes.append(
            "GPU виден в nvidia-smi, но torch.cuda недоступен — установите PyTorch с CUDA: "
            f"pip install torch torchvision --index-url https://download.pytorch.org/whl/{pip_hint}"
        )
        notes.append(
            "После установки снова: python scripts/compute_detect.py --apply-config"
        )
    if smi_ok and docker_ok and not docker_nvidia:
        notes.append(
            "Драйвер NVIDIA есть, но Docker без NVIDIA runtime — Ollama лучше запускать "
            "в режиме CPU (docker-compose.yml без gpu-файла) или установите NVIDIA Container Toolkit."
        )

    embedding_device = "cuda" if torch_ok else "cpu"

    use_ollama_gpu = smi_ok and docker_ok and docker_nvidia
    if use_ollama_gpu:
        ollama_mode = "gpu"
        compose_files = ["docker-compose.yml", "docker-compose.gpu.yml"]
    else:
        ollama_mode = "cpu"
        compose_files = ["docker-compose.yml"]
        if smi_ok and not docker_nvidia:
            notes.append("Ollama будет на CPU внутри контейнера (медленнее, но работает).")

    sys.path.insert(0, str(EMBED_DIR))
    from runtime_config import load_runtime_config  # noqa: E402
    from model_selector import select_ollama_model  # noqa: E402

    runtime_cfg = load_runtime_config()
    ollama_model, ollama_reason = select_ollama_model(
        runtime_cfg, ollama_compose_mode=ollama_mode
    )

    return ComputeReport(
        nvidia_smi=smi_ok,
        gpu_name=gpu_name,
        vram_gb=vram,
        torch_cuda=torch_ok,
        torch_cuda_device=torch_dev,
        docker_available=docker_ok,
        docker_nvidia_runtime=docker_nvidia,
        embedding_device_recommended=embedding_device,
        ollama_compose_mode=ollama_mode,
        ollama_compose_files=compose_files,
        ollama_model_recommended=ollama_model,
        ollama_model_reason=ollama_reason,
        notes=notes,
    )


def apply_embedding_device_to_config(config_path: Path, device: str) -> None:
    sys.path.insert(0, str(EMBED_DIR))
    from runtime_config import load_runtime_config  # noqa: E402

    cfg = load_runtime_config(config_path)
    cfg.setdefault("models", {})
    cfg["models"]["device_text"] = device
    cfg["models"]["device_clip"] = "cpu"
    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_runtime_summary(report: ComputeReport, *, title: str = "Режим вычислений (GPU/CPU)") -> None:
    print(f"=== {title} ===")
    gpu_line = ""
    if report.nvidia_smi and report.gpu_name:
        gpu_line = f" ({report.gpu_name}"
        if report.vram_gb is not None:
            gpu_line += f", {report.vram_gb} GB"
        gpu_line += ")"
    print(
        f"Embeddings: device_text={report.embedding_device_recommended}"
        + (f", PyTorch CUDA: {report.torch_cuda_device}" if report.torch_cuda else ", PyTorch: CPU")
        + gpu_line
    )
    print(
        f"Ollama: compose={report.ollama_compose_mode.upper()}, "
        f"модель={report.ollama_model_recommended}"
    )
    for note in report.notes:
        print(f"  • {note}")


def ensure_runtime_config(
    *,
    config_path: Path | None = None,
    apply: bool = True,
    print_report: bool = True,
) -> ComputeReport:
    """
    Детект GPU/CPU, опционально синхронизация config/rag_runtime.json с рекомендациями.
    Вызывается при старте Milvus/Ollama и из start_report_docker.py.
    """
    cfg_path = config_path or (ROOT / "config" / "rag_runtime.json")
    report = build_compute_report()
    if print_report:
        print_runtime_summary(report)
    if apply:
        apply_embedding_device_to_config(cfg_path, report.embedding_device_recommended)
        ollama_written = apply_ollama_model_to_config(
            cfg_path, report.ollama_model_recommended, only_if_auto=True
        )
        if print_report:
            print(f"Конфиг: {cfg_path.name} -> device_text={report.embedding_device_recommended}")
            if ollama_written:
                print(f"Конфиг: {cfg_path.name} -> ollama.model={report.ollama_model_recommended}")
    return report


def apply_ollama_model_to_config(
    config_path: Path, model: str, *, only_if_auto: bool = True
) -> bool:
    sys.path.insert(0, str(EMBED_DIR))
    from runtime_config import load_runtime_config  # noqa: E402

    cfg = load_runtime_config(config_path)
    if only_if_auto and not cfg.get("model_selection", {}).get("auto_select_ollama_model", False):
        return False
    cfg.setdefault("ollama", {})
    cfg["ollama"]["model"] = model
    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Проверка CUDA и рекомендации GPU/CPU.")
    parser.add_argument("--json", action="store_true", help="JSON на stdout")
    parser.add_argument(
        "--apply-config",
        action="store_true",
        help="Записать models.device_text и (при auto_select_ollama_model) ollama.model в config/rag_runtime.json",
    )
    args = parser.parse_args()

    if args.json:
        report = build_compute_report()
        if args.apply_config:
            cfg_path = ROOT / "config" / "rag_runtime.json"
            apply_embedding_device_to_config(cfg_path, report.embedding_device_recommended)
            apply_ollama_model_to_config(
                cfg_path, report.ollama_model_recommended, only_if_auto=True
            )
        payload: dict[str, Any] = asdict(report)
        payload["ollama_dir"] = str(OLLAMA_DIR)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.apply_config:
        ensure_runtime_config(apply=True, print_report=True)
        return

    report = build_compute_report()
    print("=== Проверка CUDA / GPU ===")
    print(f"nvidia-smi:        {report.nvidia_smi}" + (f" ({report.gpu_name}, {report.vram_gb} GB)" if report.gpu_name else ""))
    print(f"PyTorch CUDA:      {report.torch_cuda}" + (f" ({report.torch_cuda_device})" if report.torch_cuda_device else ""))
    print(f"Docker:            {report.docker_available}")
    print(f"Docker NVIDIA:     {report.docker_nvidia_runtime}")
    print(f"Embedding (реком.): device_text = {report.embedding_device_recommended}")
    print(f"Ollama compose:    {report.ollama_compose_mode} -> {report.ollama_compose_files}")
    print(f"Ollama LLM (реком.): {report.ollama_model_recommended}")
    print(f"  ({report.ollama_model_reason})")
    for note in report.notes:
        print(f"  • {note}")


if __name__ == "__main__":
    main()
