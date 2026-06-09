"""Optional dense-embedding support for the local Markdown knowledge base.

This module is intentionally dependency-light at import time: heavy libraries
(``sentence_transformers``, ``faiss``, ``numpy``) are imported lazily inside the
functions. If they are not installed — or a model cannot be loaded (e.g. offline,
no cached weights) — every entry point degrades gracefully and the caller falls
back to the pure-Python TF-IDF retriever.

Shared by ``build_index.py`` (encode + build FAISS index) and ``retriever.py``
(encode query + search).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "indexes"
DENSE_INDEX_PATH = INDEX_DIR / "dense.faiss"
DENSE_META_PATH = INDEX_DIR / "dense_meta.json"

# Default to a small Chinese-first model (~95MB). Override with WISE_EMBED_MODEL.
DEFAULT_MODEL = os.environ.get("WISE_EMBED_MODEL", "BAAI/bge-small-zh-v1.5").strip()

# bge-zh models are trained to use a query-side instruction for retrieval.
_BGE_ZH_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

_model = None  # cached SentenceTransformer instance
_model_failed = False
_model_name_loaded: Optional[str] = None


def embeddings_enabled() -> bool:
    """Whether dense retrieval is allowed (escape hatch via WISE_EMBED_ENABLED=0)."""
    return os.environ.get("WISE_EMBED_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def deps_available() -> bool:
    import importlib.util

    return all(importlib.util.find_spec(name) for name in ("sentence_transformers", "faiss", "numpy"))


def model_name() -> str:
    return _model_name_loaded or DEFAULT_MODEL


def load_model(name: Optional[str] = None):
    """Lazily load + cache the embedding model. Returns ``None`` on any failure."""
    global _model, _model_failed, _model_name_loaded
    target = (name or DEFAULT_MODEL).strip()
    if _model is not None and _model_name_loaded == target:
        return _model
    if _model_failed:
        return None
    if not embeddings_enabled() or not deps_available():
        _model_failed = True
        return None
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(target)
        _model_name_loaded = target
        return _model
    except Exception as exc:  # offline / missing weights / OOM
        print(f"[embedding] model load failed ({target}): {exc}")
        _model_failed = True
        return None


def _query_instruction(name: str) -> str:
    lowered = (name or "").lower()
    if "bge" in lowered and ("zh" in lowered or "chinese" in lowered):
        return _BGE_ZH_QUERY_INSTRUCTION
    return ""


def encode_documents(model, texts: List[str]):
    """Return an (N, dim) float32 matrix of L2-normalized document embeddings."""
    import numpy as np

    emb = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=32,
        show_progress_bar=False,
    )
    return np.asarray(emb, dtype="float32")


def encode_query(model, text: str, name: Optional[str] = None):
    """Return a (1, dim) float32 normalized query embedding."""
    import numpy as np

    instruction = _query_instruction(name or model_name())
    emb = model.encode(
        [instruction + text],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(emb, dtype="float32")
