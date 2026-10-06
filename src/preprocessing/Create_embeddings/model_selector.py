# -*- coding: utf-8 -*-
"""Автоматический выбор embedding- и Ollama-моделей по возможностям GPU."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from runtime_config import ROOT


MODEL_PROFILES_PATH = ROOT / "config" / "model_profiles.json"


@dataclass
class GpuInfo:
    name: str
    vram_gb: float
    source: str


def _load_model_profiles(path: Path = MODEL_PROFILES_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {"default_profile": "", "profiles": [], "gpu_name_overrides": {}}

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                return raw
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {"default_profile": "", "profiles": [], "gpu_name_overrides": {}}


def _detect_gpu_via_nvidia_smi() -> Optional[GpuInfo]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        first_line = (result.stdout or "").strip().splitlines()[0]
        name_part, memory_mb_part = [p.strip() for p in first_line.split(",", 1)]
        vram_gb = round(float(memory_mb_part) / 1024.0, 2)
        return GpuInfo(name=name_part, vram_gb=vram_gb, source="nvidia-smi")
    except (IndexError, ValueError, OSError):
        return None


def _detect_gpu_via_torch() -> Optional[GpuInfo]:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        props = torch.cuda.get_device_properties(0)
        vram_gb = round(float(props.total_memory) / (1024**3), 2)
        return GpuInfo(name=props.name, vram_gb=vram_gb, source="torch.cuda")
    except Exception:
        return None


def detect_gpu_info() -> Optional[GpuInfo]:
    return _detect_gpu_via_nvidia_smi() or _detect_gpu_via_torch()


def _find_profile_by_name(profiles: List[Dict[str, Any]], profile_name: str) -> Optional[Dict[str, Any]]:
    for profile in profiles:
        if profile.get("name") == profile_name:
            return profile
    return None


def _match_profile_by_vram(profiles: List[Dict[str, Any]], vram_gb: float) -> Optional[Dict[str, Any]]:
    for profile in profiles:
        match = profile.get("match", {})
        min_vram = match.get("min_vram_gb")
        max_vram = match.get("max_vram_gb")
        if min_vram is not None and vram_gb < float(min_vram):
            continue
        if max_vram is not None and vram_gb > float(max_vram):
            continue
        return profile
    return None


def select_text_model(runtime_cfg: Dict[str, Any]) -> Tuple[str, str]:
    """
    Возвращает (model_name, reason) для текстовых эмбеддингов.

    Порядок:
    1) auto_select_text_model=False -> models.text_model_name
    2) GPU override по имени
    3) GPU match по VRAM
    4) default_profile из model_profiles.json
    5) fallback models.text_model_name
    """
    return _resolve_profile_model(
        runtime_cfg,
        profile_field="text_model",
        auto_flag="auto_select_text_model",
        fallback_key=("models", "text_model_name"),
        fallback_default="intfloat/multilingual-e5-base",
    )


def _resolve_profile_model(
    runtime_cfg: Dict[str, Any],
    *,
    profile_field: str,
    auto_flag: str,
    fallback_key: tuple[str, ...],
    fallback_default: str,
    ollama_compose_mode: str = "gpu",
) -> Tuple[str, str]:
    """Общая логика выбора модели по GPU-профилю (text_model / ollama_model)."""
    model_selection = runtime_cfg.get("model_selection", {})
    if not model_selection.get(auto_flag, False):
        block: Any = runtime_cfg
        for key in fallback_key:
            block = block.get(key, {}) if isinstance(block, dict) else {}
        value = block if isinstance(block, str) and block else fallback_default
        return value, f"{auto_flag} disabled in config"

    profiles_data = _load_model_profiles()
    profiles = profiles_data.get("profiles", [])
    overrides = profiles_data.get("gpu_name_overrides", {})
    default_profile_name = profiles_data.get("default_profile", "")

    fallback_block: Any = runtime_cfg
    for key in fallback_key:
        fallback_block = fallback_block.get(key, {}) if isinstance(fallback_block, dict) else {}
    fallback_model = (
        fallback_block if isinstance(fallback_block, str) and fallback_block else fallback_default
    )

    if ollama_compose_mode == "cpu" and profile_field == "ollama_model":
        cpu_model = profiles_data.get("ollama_fallback_cpu_compose")
        if cpu_model:
            return cpu_model, "ollama CPU compose (Docker без GPU runtime)"
        default_profile = _find_profile_by_name(profiles, default_profile_name)
        if default_profile and default_profile.get(profile_field):
            return default_profile[profile_field], "ollama CPU compose, default profile"

    gpu_info = detect_gpu_info()
    if gpu_info is None:
        default_profile = _find_profile_by_name(profiles, default_profile_name)
        if default_profile and default_profile.get(profile_field):
            return default_profile[profile_field], "gpu not detected, using default profile"
        return fallback_model, "gpu not detected, using fallback from rag_runtime.json"

    gpu_name_l = gpu_info.name.lower()
    for gpu_name_pattern, profile_name in overrides.items():
        if gpu_name_pattern.lower() in gpu_name_l:
            profile = _find_profile_by_name(profiles, profile_name)
            if profile and profile.get(profile_field):
                return (
                    profile[profile_field],
                    f"gpu override matched ({gpu_info.name}, {gpu_info.vram_gb}GB, {gpu_info.source})",
                )

    matched = _match_profile_by_vram(profiles, gpu_info.vram_gb)
    if matched and matched.get(profile_field):
        return (
            matched[profile_field],
            f"vram profile matched ({gpu_info.name}, {gpu_info.vram_gb}GB, {gpu_info.source})",
        )

    default_profile = _find_profile_by_name(profiles, default_profile_name)
    if default_profile and default_profile.get(profile_field):
        return default_profile[profile_field], "using default profile from model_profiles.json"

    return fallback_model, "using fallback from rag_runtime.json"


def select_ollama_model(
    runtime_cfg: Dict[str, Any],
    *,
    ollama_compose_mode: str = "gpu",
) -> Tuple[str, str]:
    """
    Возвращает (ollama_model_tag, reason).

    Порядок как у select_text_model; поле профиля — ollama_model.
    При ollama_compose_mode=cpu — ollama_fallback_cpu_compose или профиль по умолчанию.
    """
    return _resolve_profile_model(
        runtime_cfg,
        profile_field="ollama_model",
        auto_flag="auto_select_ollama_model",
        fallback_key=("ollama", "model"),
        fallback_default="qwen2.5:3b",
        ollama_compose_mode=ollama_compose_mode,
    )
