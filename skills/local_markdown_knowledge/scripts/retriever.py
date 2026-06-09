"""Hybrid retriever for the local Markdown knowledge base.

Combines a pure-Python sparse retriever (TF-IDF cosine) with an optional dense
retriever (sentence-transformers + FAISS). Rankings are fused with Reciprocal
Rank Fusion (RRF); the reported ``score`` stays a real similarity in [0, 1] so
existing downstream thresholds keep working.

If the dense index / embedding deps are unavailable, it transparently falls back
to the original TF-IDF-only behaviour.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Make sibling modules importable whether run as a subprocess or via importlib.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedding as emb  # noqa: E402  (lazy heavy deps; import never fails)


BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "indexes"

RRF_K = 60          # standard RRF damping constant
CANDIDATES = 50     # per-branch candidates considered for fusion
# Dense cosine has a high "similarity floor" (esp. Chinese models); rescale it to
# [0,1] so the reported score is comparable with the sparse cosine and the
# downstream 0.18 gate. Tune the floor with WISE_EMBED_FLOOR.
DENSE_FLOOR = float(os.environ.get("WISE_EMBED_FLOOR", "0.35"))
DENSE_CEIL = 0.90


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9_./:-]+|[一-鿿]", lowered)
    return [word for word in words if word.strip()]


class _DenseIndex:
    """Thin wrapper over a FAISS index + embedding model. Row i maps to chunks[i]."""

    def __init__(self, index, model, name: str):
        self.index = index
        self.model = model
        self.name = name

    @classmethod
    def load(cls, chunk_count: int) -> Optional["_DenseIndex"]:
        if not emb.embeddings_enabled() or not emb.deps_available():
            return None
        if not emb.DENSE_INDEX_PATH.exists() or not emb.DENSE_META_PATH.exists():
            return None
        try:
            with emb.DENSE_META_PATH.open("r", encoding="utf-8") as f:
                meta = json.load(f)
            # Guard against a stale dense index that no longer matches the chunks.
            if int(meta.get("count", -1)) != chunk_count:
                return None
            model = emb.load_model(meta.get("model"))
            if model is None:
                return None
            import faiss

            index = faiss.read_index(str(emb.DENSE_INDEX_PATH))
            if index.ntotal != chunk_count:
                return None
            return cls(index, model, meta.get("model") or emb.model_name())
        except Exception as exc:  # corrupt index, dim mismatch, etc.
            print(f"[retriever] dense index unavailable: {exc}")
            return None

    def search(self, query: str, top_n: int) -> List[Tuple[int, float]]:
        vector = emb.encode_query(self.model, query, self.name)
        scores, ids = self.index.search(vector, top_n)
        out: List[Tuple[int, float]] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx >= 0:
                out.append((int(idx), float(score)))
        return out


def _rescale_dense(cosine: float) -> float:
    if cosine <= DENSE_FLOOR:
        return 0.0
    return min(1.0, (cosine - DENSE_FLOOR) / (DENSE_CEIL - DENSE_FLOOR))


class LocalMarkdownRetriever:
    def __init__(self) -> None:
        chunks_path = INDEX_DIR / "chunks.jsonl"
        idf_path = INDEX_DIR / "idf.json"
        if not chunks_path.exists() or not idf_path.exists():
            raise FileNotFoundError("Missing local Markdown index. Run scripts/build_index.py first.")

        self.chunks: List[Dict[str, Any]] = []
        with chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                self.chunks.append(json.loads(line))

        with idf_path.open("r", encoding="utf-8") as f:
            self.idf = json.load(f)

        self._dense = _DenseIndex.load(len(self.chunks))

    @property
    def hybrid_enabled(self) -> bool:
        return self._dense is not None

    def _sparse_scores(self, query: str) -> Dict[int, float]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return {}
        query_weights = {token: self.idf.get(token, 1.0) for token in query_tokens}
        query_norm = math.sqrt(sum(w * w for w in query_weights.values())) or 1.0
        scores: Dict[int, float] = {}
        for i, chunk in enumerate(self.chunks):
            counts = chunk.get("token_counts", {})
            dot = 0.0
            doc_norm = 0.0
            for token, count in counts.items():
                weight = float(count) * self.idf.get(token, 1.0)
                doc_norm += weight * weight
                if token in query_weights:
                    dot += weight * query_weights[token]
            if dot > 0:
                scores[i] = dot / (query_norm * (math.sqrt(doc_norm) or 1.0))
        return scores

    def _format(self, idx: int, score: float) -> Dict[str, Any]:
        chunk = self.chunks[idx]
        return {
            "chunk_id": chunk["chunk_id"],
            "score": round(float(score), 4),
            "source": chunk["file_path"],
            "heading": chunk["heading_path"],
            "content": chunk["content"],
        }

    def search(self, query: str, top_k: int = 5, min_score: float = 0.12) -> List[Dict[str, Any]]:
        sparse_scores = self._sparse_scores(query)
        sparse_ranked = sorted(sparse_scores, key=lambda i: sparse_scores[i], reverse=True)

        dense_hits: List[Tuple[int, float]] = []
        if self._dense is not None and query.strip():
            try:
                dense_hits = self._dense.search(query, max(top_k * 5, CANDIDATES))
            except Exception as exc:
                print(f"[retriever] dense search failed, using sparse only: {exc}")
                dense_hits = []
        dense_scores = {idx: cos for idx, cos in dense_hits}
        dense_ranked = [idx for idx, _ in dense_hits]

        # --- fallback: sparse-only (preserves original behaviour) ---
        if not dense_ranked:
            results = []
            for idx in sparse_ranked:
                cosine = sparse_scores[idx]
                if cosine >= min_score:
                    results.append(self._format(idx, cosine))
                if len(results) >= top_k:
                    break
            return results

        # --- hybrid: Reciprocal Rank Fusion over both rankings ---
        rrf: Dict[int, float] = {}
        for rank, idx in enumerate(sparse_ranked[:CANDIDATES], start=1):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (RRF_K + rank)
        for rank, idx in enumerate(dense_ranked[:CANDIDATES], start=1):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (RRF_K + rank)

        fused = sorted(rrf, key=lambda i: rrf[i], reverse=True)
        results = []
        for idx in fused:
            similarity = max(sparse_scores.get(idx, 0.0), _rescale_dense(dense_scores.get(idx, 0.0)))
            # Relevance floor so weak (high-baseline) dense matches don't leak noise.
            if similarity < min_score:
                continue
            results.append(self._format(idx, similarity))
            if len(results) >= top_k:
                break
        return results


_retriever: LocalMarkdownRetriever | None = None


def retrieve_local_markdown_knowledge(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    global _retriever
    if _retriever is None:
        _retriever = LocalMarkdownRetriever()
    return _retriever.search(query=query, top_k=top_k)


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "如何处理登录失败？"
    print(json.dumps(retrieve_local_markdown_knowledge(question), ensure_ascii=False, indent=2))
