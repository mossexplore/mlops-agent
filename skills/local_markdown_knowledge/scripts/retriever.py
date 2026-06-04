from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "indexes"


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9_./:-]+|[\u4e00-\u9fff]", lowered)
    return [word for word in words if word.strip()]


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

    def search(self, query: str, top_k: int = 5, min_score: float = 0.12) -> List[Dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        query_weights = {token: self.idf.get(token, 1.0) for token in query_tokens}
        query_norm = math.sqrt(sum(weight * weight for weight in query_weights.values())) or 1.0
        scored = []

        for chunk in self.chunks:
            counts = chunk.get("token_counts", {})
            score = 0.0
            doc_norm = 0.0
            for token, count in counts.items():
                weight = float(count) * self.idf.get(token, 1.0)
                doc_norm += weight * weight
                if token in query_weights:
                    score += weight * query_weights[token]
            normalized = score / (query_norm * (math.sqrt(doc_norm) or 1.0))
            if normalized >= min_score:
                scored.append((normalized, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "chunk_id": chunk["chunk_id"],
                "score": round(float(score), 4),
                "source": chunk["file_path"],
                "heading": chunk["heading_path"],
                "content": chunk["content"],
            }
            for score, chunk in scored[:top_k]
        ]


_retriever: LocalMarkdownRetriever | None = None


def retrieve_local_markdown_knowledge(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    global _retriever
    if _retriever is None:
        _retriever = LocalMarkdownRetriever()
    return _retriever.search(query=query, top_k=top_k)


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) or "如何处理登录失败？"
    print(json.dumps(retrieve_local_markdown_knowledge(question), ensure_ascii=False, indent=2))
