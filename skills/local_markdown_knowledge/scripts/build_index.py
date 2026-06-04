from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from markdown_loader import load_markdown_chunks


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

    print(f"Indexed {len(chunks)} chunks.")
    print(f"Index saved to {INDEX_DIR}")


if __name__ == "__main__":
    main()
