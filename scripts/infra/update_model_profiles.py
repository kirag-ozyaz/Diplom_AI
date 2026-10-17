#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обновляет список кандидатов моделей в config/model_profiles.json."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import URLError, HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
MODEL_PROFILES_PATH = ROOT / "config" / "model_profiles.json"
EMBEDDING_CONFIG_PATH = ROOT / "src" / "preprocessing" / "Create_embeddings" / "embedding_config.json"

USER_AGENT = "energy-norms-bot-model-updater/1.0"

RAG_KEYWORDS = (
    "embed",
    "embedding",
    "bge",
    "e5",
    "gte",
    "minilm",
    "mpnet",
    "nomic",
    "jina",
    "mxbai",
    "reranker",
    "rerank",
)

# Чтобы не тащить случайные тонкие дообучения, ограничиваемся
# известными поставщиками embedding/IR-моделей.
TRUSTED_HF_PREFIXES = (
    "sentence-transformers/",
    "baai/",
    "intfloat/",
    "alibaba-nlp/",
    "jinaai/",
    "nomic-ai/",
    "mixedbread-ai/",
    "cohere/",
    "thenlper/",
    "xenova/",
    "lightonai/",
    "onnx-community/",
    "supabase/",
    "microsoft/",
)

# Закреплённые модели из мартовского хелпа:
# всегда присутствуют в общем списке candidates,
# не удаляются и не перезаписываются автообновлением.
PINNED_HELP_MODELS: List[Dict[str, Any]] = [
    {"model": "intfloat/multilingual-e5-base", "note": "качество для русского+английского", "dim": 768},
    {"model": "BAAI/bge-m3", "note": "мультиязычная, сильный retrieval", "dim": 1024},
    {"model": "Cohere/embed-multilingual-light-v3.0", "note": "легкая мультиязычная", "dim": 384},
    {"model": "jinaai/jina-embeddings-v3", "note": "мультиязычная, длинный контекст", "dim": 1024},
    {"model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "note": "быстрая мультиязычная"},
    {"model": "sentence-transformers/LaBSE", "note": "классическая multilingual-модель"},
]

PINNED_HELP_SET = {item["model"].lower() for item in PINNED_HELP_MODELS}


def _is_russian_or_multilingual(model_id: str) -> bool:
    mid = model_id.lower()
    if mid in PINNED_HELP_SET:
        return True
    multilingual_tokens = (
        "multilingual",
        "bge-m3",
        "labse",
        "jina-embeddings-v3",
        "jina-embeddings-v4",
        "jina-embeddings-v5",
        "rubert",
        "russian",
    )
    return any(tok in mid for tok in multilingual_tokens)


def _build_pinned_candidates() -> List[Dict[str, Any]]:
    pinned: List[Dict[str, Any]] = []
    for item in PINNED_HELP_MODELS:
        cand: Dict[str, Any] = {
            "provider": "huggingface",
            "model": item["model"],
            "kind": "embedding",
            "source": "pinned_help",
            "pinned": True,
            "note": item.get("note", ""),
        }
        if "dim" in item:
            cand["dim"] = int(item["dim"])
        pinned.append(cand)
    return pinned


def _extract_existing_pinned(profiles: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    existing = profiles.get("candidates", [])
    if not isinstance(existing, list):
        return out
    for item in existing:
        if isinstance(item, dict) and item.get("pinned") is True:
            out.append(item)
    return out


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _fetch_json(url: str, timeout_sec: int = 15) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _fetch_text(url: str, timeout_sec: int = 15) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout_sec) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _collect_from_embedding_config() -> List[Dict[str, Any]]:
    emb = _read_json(EMBEDDING_CONFIG_PATH, {})
    model_dim = emb.get("text_model_dim", {}) if isinstance(emb, dict) else {}
    candidates = []
    for model_name, dim in model_dim.items():
        if not _is_russian_or_multilingual(model_name):
            continue
        candidates.append(
            {
                "provider": "huggingface",
                "model": model_name,
                "kind": "embedding",
                "dim": int(dim),
                "source": "embedding_config",
            }
        )
    return candidates


def _collect_from_huggingface(max_per_query: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    queries = ["sentence-transformers", "e5", "bge", "gte", "jina-embeddings", "nomic-embed", "mxbai-embed"]
    candidates: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    allow_pattern = re.compile(r"(embed|embedding|bge|e5|gte|minilm|mpnet|nomic|jina|mxbai|reranker|rerank)", re.IGNORECASE)

    for q in queries:
        url = f"https://huggingface.co/api/models?search={quote_plus(q)}&limit={max_per_query}"
        try:
            data = _fetch_json(url)
            if not isinstance(data, list):
                continue
            for item in data:
                model_id = item.get("modelId")
                if not model_id or not isinstance(model_id, str):
                    continue
                model_id_l = model_id.lower()
                if not model_id_l.startswith(TRUSTED_HF_PREFIXES):
                    continue
                if not allow_pattern.search(model_id):
                    continue
                if not _is_russian_or_multilingual(model_id):
                    continue
                existing = candidates.get(model_id)
                downloads = int(item.get("downloads") or 0)
                # Базовый порог, чтобы отсечь шумные/случайные модели.
                if downloads < 1000:
                    continue
                if existing is None or downloads > existing.get("downloads", 0):
                    candidates[model_id] = {
                        "provider": "huggingface",
                        "model": model_id,
                        "kind": "embedding",
                        "downloads": downloads,
                        "source": "huggingface_api",
                    }
        except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"huggingface query '{q}': {exc}")

    return sorted(candidates.values(), key=lambda x: x.get("downloads", 0), reverse=True), errors


def _collect_from_ollama(max_items: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    try:
        html = _fetch_text("https://ollama.com/library")
        slugs = set(re.findall(r'href="/library/([^"#?/\s]+)"', html))
        models = []
        for slug in sorted(slugs):
            if slug in {"library", "search"}:
                continue
            slug_l = slug.lower()
            if not any(k in slug_l for k in RAG_KEYWORDS):
                continue
            if "bge-m3" not in slug_l and "multilingual" not in slug_l:
                continue
            models.append(
                {
                    "provider": "ollama",
                    "model": slug,
                    "kind": "embedding_or_rag",
                    "source": "ollama_library",
                }
            )
        return models[:max_items], errors
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        errors.append(f"ollama library: {exc}")
        return [], errors


def _dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for cand in candidates:
        provider = str(cand.get("provider", "")).strip().lower()
        model = str(cand.get("model", "")).strip()
        if not provider or not model:
            continue
        key = (provider, model)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = cand
            continue
        if cand.get("pinned") is True and existing.get("pinned") is not True:
            by_key[key] = cand
            continue
        if existing.get("pinned") is True and cand.get("pinned") is not True:
            continue
        # Предпочитаем запись, где есть dim, затем где больше downloads.
        if existing.get("dim") is None and cand.get("dim") is not None:
            by_key[key] = cand
            continue
        if int(cand.get("downloads", 0)) > int(existing.get("downloads", 0)):
            by_key[key] = cand
    return sorted(by_key.values(), key=lambda x: (x.get("provider", ""), x.get("model", "")))


def update_model_profiles(max_hf_per_query: int, max_ollama_models: int) -> Dict[str, Any]:
    profiles = _read_json(MODEL_PROFILES_PATH, {})
    if not isinstance(profiles, dict):
        profiles = {}

    local_candidates = _collect_from_embedding_config()
    hf_candidates, hf_errors = _collect_from_huggingface(max_hf_per_query)
    ollama_candidates, ollama_errors = _collect_from_ollama(max_ollama_models)
    pinned_candidates = _build_pinned_candidates()
    existing_pinned = _extract_existing_pinned(profiles)

    merged_candidates = _dedupe_candidates(
        local_candidates + hf_candidates + ollama_candidates + pinned_candidates + existing_pinned
    )

    profiles["candidates"] = merged_candidates
    profiles.pop("march_help_reference", None)
    profiles["candidate_refresh"] = {
        "updated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_candidates": len(merged_candidates),
        "sources": {
            "embedding_config": len(local_candidates),
            "huggingface_api": len(hf_candidates),
            "ollama_library": len(ollama_candidates),
            "pinned_help": len(pinned_candidates),
        },
        "errors": hf_errors + ollama_errors,
    }

    MODEL_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return profiles["candidate_refresh"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Обновление candidates в config/model_profiles.json из локального и онлайн-источников."
    )
    parser.add_argument("--max-hf-per-query", type=int, default=40, help="Лимит моделей HF на каждый поисковый запрос")
    parser.add_argument("--max-ollama-models", type=int, default=120, help="Максимум моделей из Ollama Library")
    args = parser.parse_args()

    summary = update_model_profiles(
        max_hf_per_query=max(1, args.max_hf_per_query),
        max_ollama_models=max(1, args.max_ollama_models),
    )

    print("model_profiles.json updated")
    print(f"total candidates: {summary['total_candidates']}")
    print(f"sources: {summary['sources']}")
    if summary["errors"]:
        print("warnings:")
        for err in summary["errors"]:
            print(f"- {err}")


if __name__ == "__main__":
    main()
