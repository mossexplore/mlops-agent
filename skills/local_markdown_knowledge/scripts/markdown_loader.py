from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class MarkdownChunk:
    chunk_id: str
    file_path: str
    heading_path: str
    content: str


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_heading_path(current_headings: dict[int, str]) -> str:
    return " > ".join(current_headings[level] for level in sorted(current_headings))


def split_markdown_file(file_path: Path, max_chars: int = 1200, overlap: int = 150) -> List[MarkdownChunk]:
    text = normalize_text(file_path.read_text(encoding="utf-8"))
    lines = text.split("\n")
    chunks: List[MarkdownChunk] = []
    current_headings: dict[int, str] = {}
    buffer: list[str] = []
    chunk_index = 0

    def flush_buffer() -> None:
        nonlocal buffer, chunk_index
        content = normalize_text("\n".join(buffer))
        if not content:
            buffer = []
            return

        start = 0
        while start < len(content):
            end = min(start + max_chars, len(content))
            piece = content[start:end].strip()
            if piece:
                chunks.append(
                    MarkdownChunk(
                        chunk_id=f"{file_path.name}:{chunk_index}",
                        file_path=str(file_path),
                        heading_path=extract_heading_path(current_headings),
                        content=piece,
                    )
                )
                chunk_index += 1
            if end >= len(content):
                break
            start = max(0, end - overlap)
        buffer = []

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            flush_buffer()
            level = len(heading_match.group(1))
            current_headings[level] = heading_match.group(2).strip()
            for old_level in list(current_headings):
                if old_level > level:
                    del current_headings[old_level]
        buffer.append(line)

    flush_buffer()
    return chunks


def load_markdown_chunks(knowledge_dir: str | Path) -> List[MarkdownChunk]:
    knowledge_dir = Path(knowledge_dir)
    all_chunks: List[MarkdownChunk] = []
    for file_path in sorted(knowledge_dir.rglob("*.md")):
        all_chunks.extend(split_markdown_file(file_path))
    return all_chunks
