from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database import (
    get_knowledge_file,
    list_knowledge_files,
    list_knowledge_gaps,
    list_knowledge_revisions,
    update_knowledge_status,
    upsert_knowledge_file,
)


BASE_DIR = Path(__file__).resolve().parent.parent
SKILL_DIR = BASE_DIR / "skills" / "local_markdown_knowledge"
KNOWLEDGE_DIR = SKILL_DIR / "knowledge"
INDEX_DIR = SKILL_DIR / "indexes"
BUILD_SCRIPT = SKILL_DIR / "scripts" / "build_index.py"
RETRIEVER_SCRIPT = SKILL_DIR / "scripts" / "retriever.py"


def ensure_knowledge_dirs() -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def slugify_filename(title: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", title.strip().lower())
    normalized = normalized.strip("-._")
    return f"{normalized or 'knowledge'}.md"


def safe_markdown_filename(filename: Optional[str], title: str) -> str:
    candidate = filename or slugify_filename(title)
    candidate = Path(candidate).name
    if not candidate.endswith(".md"):
        candidate += ".md"
    if candidate in {".md", "..md"}:
        candidate = slugify_filename(title)
    return candidate


def extract_title(text: str, fallback: str) -> str:
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return title_match.group(1).strip() if title_match else fallback


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def timestamp_from_path(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def apply_title_to_markdown(title: str, markdown: str, fallback: str) -> str:
    clean_title = title.strip() or fallback
    stripped = markdown.strip()
    if re.search(r"^#\s+.+$", stripped, re.MULTILINE):
        return re.sub(r"^#\s+.+$", f"# {clean_title}", stripped, count=1, flags=re.MULTILINE)
    return f"# {clean_title}\n\n{stripped}"


def record_markdown_file(path: Path, create_revision: bool = False) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title = extract_title(text, path.stem)
    return upsert_knowledge_file(
        filename=path.name,
        title=title,
        file_path=str(path),
        content=text,
        content_hash=content_hash(text),
        size=path.stat().st_size,
        preview=text[:240],
        create_revision=create_revision,
        timestamp=None if create_revision else timestamp_from_path(path),
    )


def sync_markdown_files_to_db() -> None:
    ensure_knowledge_dirs()
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        record_markdown_file(path, create_revision=False)


def write_markdown_knowledge(
    title: str,
    content: str,
    filename: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    visibility: Optional[str] = None,
    review_notes: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_knowledge_dirs()
    safe_name = safe_markdown_filename(filename, title)
    path = KNOWLEDGE_DIR / safe_name
    markdown = apply_title_to_markdown(title, content, safe_name.removesuffix(".md"))
    path.write_text(markdown + "\n", encoding="utf-8")
    record = upsert_knowledge_file(
        filename=path.name,
        title=extract_title(markdown, path.stem),
        file_path=str(path),
        content=markdown + "\n",
        content_hash=content_hash(markdown + "\n"),
        size=path.stat().st_size,
        preview=(markdown + "\n")[:240],
        category=category,
        tags=tags,
        status=status,
        owner=owner,
        visibility=visibility,
        review_notes=review_notes,
        create_revision=True,
        action="save",
    )
    if record["status"] == "published":
        rebuild_index()
    return record


def list_markdown_knowledge() -> List[Dict[str, Any]]:
    sync_markdown_files_to_db()
    return list_knowledge_files()


def list_markdown_knowledge_revisions(filename: Optional[str] = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    return list_knowledge_revisions(filename=filename, page=page, page_size=page_size)


def get_markdown_knowledge_detail(filename: str) -> Dict[str, Any]:
    ensure_knowledge_dirs()
    safe_name = safe_markdown_filename(filename, filename)
    path = KNOWLEDGE_DIR / safe_name
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {safe_name}")

    record = record_markdown_file(path, create_revision=False)
    record["content"] = path.read_text(encoding="utf-8")
    return record


def change_markdown_knowledge_status(filename: str, status: str, review_notes: Optional[str] = None) -> Dict[str, Any]:
    safe_name = safe_markdown_filename(filename, filename)
    record = update_knowledge_status(safe_name, status=status, review_notes=review_notes)
    if record is None:
        raise FileNotFoundError(f"Knowledge file not found: {safe_name}")
    rebuild_index()
    return record


def list_markdown_knowledge_gaps(page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    return list_knowledge_gaps(page=page, page_size=page_size)


def rebuild_index() -> None:
    ensure_knowledge_dirs()
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=str(SKILL_DIR), check=True)
    reset_retriever_cache()


def _load_retriever_module():
    spec = importlib.util.spec_from_file_location("local_markdown_retriever", RETRIEVER_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load local Markdown retriever.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_retriever_module = None


def reset_retriever_cache() -> None:
    global _retriever_module
    _retriever_module = None


def retrieve_knowledge(query: str, top_k: int = 5, published_only: bool = True) -> List[Dict[str, Any]]:
    global _retriever_module
    if not (INDEX_DIR / "chunks.jsonl").exists():
        return []
    if _retriever_module is None:
        _retriever_module = _load_retriever_module()
    try:
        results = _retriever_module.retrieve_local_markdown_knowledge(query=query, top_k=max(top_k * 3, top_k))
        if published_only:
            filtered = []
            for item in results:
                record = get_knowledge_file(Path(item.get("source", "")).name)
                if record and record.get("status") == "published":
                    item["status"] = record["status"]
                    item["category"] = record["category"]
                    item["tags"] = record["tags"]
                    filtered.append(item)
            return filtered[:top_k]
        return results[:top_k]
    except FileNotFoundError:
        return []


def should_use_local_knowledge(query: str, results: List[Dict[str, Any]]) -> bool:
    if not results:
        return False
    explicit_keywords = ("知识库", "文档", "手册", "流程", "规范", "faq", "FAQ", "内部")
    if any(keyword in query for keyword in explicit_keywords):
        return True
    return results[0].get("score", 0) >= 0.18


def build_grounded_answer(query: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return "我在本地 Markdown 知识库中没有找到足够相关的信息，无法基于现有知识库可靠回答这个问题。"

    lines = [
        "### 根据本地知识库检索结果",
        "",
        f"问题：{query}",
        "",
        "以下回答仅基于命中的 Markdown 知识片段：",
        "",
    ]
    for index, item in enumerate(results[:3], start=1):
        heading = item.get("heading") or "未命名章节"
        content = item.get("content", "").strip()
        lines.extend(
            [
                f"{index}. **{heading}**",
                content,
                "",
            ]
        )

    seen = set()
    sources = []
    for item in results:
        source = Path(item.get("source", "")).name
        heading = item.get("heading") or "未命名章节"
        key = (source, heading)
        if key not in seen:
            seen.add(key)
            sources.append(f"- `{source}` > `{heading}`")

    if sources:
        lines.extend(["来源:", *sources])
    return "\n".join(lines).strip()


try:
    from langchain_core.tools import tool
except Exception:  # pragma: no cover - optional integration
    tool = None


def search_local_knowledge(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    return retrieve_knowledge(query=query, top_k=top_k)


if tool is not None:  # pragma: no cover - optional integration
    langchain_search_local_knowledge = tool(search_local_knowledge)
else:
    langchain_search_local_knowledge = search_local_knowledge
