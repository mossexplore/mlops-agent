from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from markdown_loader import load_markdown_chunks

# Make sibling modules importable whether run as a subprocess or imported.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedding as emb  # noqa: E402  (lazy heavy deps; import never fails)


BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
INDEX_DIR = BASE_DIR / "indexes"


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9_./:-]+|[\u4e00-\u9fff]", lowered)
    return [word for word in words if word.strip()]


def main() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunks = load_markdown_chunks(KNOWLEDGE_DIR)

    doc_freq: dict[str, int] = defaultdict(int)
    chunk_tokens = []
    for chunk in chunks:
        tokens = tokenize(f"{chunk.heading_path}\n{chunk.content}")
        chunk_tokens.append(tokens)
        for token in set(tokens):
            doc_freq[token] += 1

    total = max(len(chunks), 1)
    idf = {token: math.log((1 + total) / (1 + freq)) + 1 for token, freq in doc_freq.items()}

    with (INDEX_DIR / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for chunk, tokens in zip(chunks, chunk_tokens):
            payload = chunk.__dict__.copy()
            payload["token_counts"] = Counter(tokens)
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    with (INDEX_DIR / "idf.json").open("w", encoding="utf-8") as f:
        json.dump(idf, f, ensure_ascii=False, indent=2)

    print(f"Indexed {len(chunks)} chunks (sparse TF-IDF).")
    print(f"Index saved to {INDEX_DIR}")

    build_dense_index(chunks)


def _cleanup_dense(reason: str) -> None:
    """Remove any stale dense index so the retriever never reads a mismatched one."""
    for path in (emb.DENSE_INDEX_PATH, emb.DENSE_META_PATH):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    print(f"Dense index skipped: {reason}")


def build_dense_index(chunks) -> None:
    """Best-effort FAISS dense index. Any failure falls back to TF-IDF only."""
    if not emb.embeddings_enabled():
        _cleanup_dense("disabled via WISE_EMBED_ENABLED")
        return
    if not emb.deps_available():
        _cleanup_dense("sentence-transformers / faiss / numpy not installed")
        return
    if not chunks:
        _cleanup_dense("no chunks to embed")
        return
    model = emb.load_model()
    if model is None:
        _cleanup_dense("embedding model unavailable (offline or load error)")
        return
    try:
        import faiss

        texts = [f"{chunk.heading_path}\n{chunk.content}" for chunk in chunks]
        vectors = emb.encode_documents(model, texts)
        dim = int(vectors.shape[1])
        index = faiss.IndexFlatIP(dim)  # inner product == cosine on normalized vectors
        index.add(vectors)
        faiss.write_index(index, str(emb.DENSE_INDEX_PATH))
        meta = {"model": emb.model_name(), "dim": dim, "count": len(chunks)}
        with emb.DENSE_META_PATH.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        print(f"Dense index built: {len(chunks)} chunks, dim={dim}, model={emb.model_name()}")
    except Exception as exc:  # never let dense break the (sparse) build
        _cleanup_dense(f"build error: {exc}")


if __name__ == "__main__":
    main()
