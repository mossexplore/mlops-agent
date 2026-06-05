import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import settings

DB_PATH = settings.db_path


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_text() -> str:
    return date.today().isoformat()


def default_start_date_text(days: int = 6) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


@contextmanager
def connect(db_path: Optional[Path] = None) -> Iterable[sqlite3.Connection]:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS t_conversation (
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              title TEXT NOT NULL,
              timestamp TEXT,
              PRIMARY KEY (user_id, conversation_id)
            );

            CREATE TABLE IF NOT EXISTS t_chat_memory (
              memory_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              type TEXT NOT NULL,
              content TEXT NOT NULL,
              timestamp TEXT,
              PRIMARY KEY (memory_id, user_id, conversation_id)
            );

            CREATE TABLE IF NOT EXISTS t_conversation_context (
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              service TEXT NOT NULL,
              scene TEXT NOT NULL,
              timestamp TEXT,
              PRIMARY KEY (user_id, conversation_id)
            );

            CREATE TABLE IF NOT EXISTS t_chat_feedback (
              answer_message_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              query_message_id TEXT,
              feedback TEXT NOT NULL,
              reason TEXT,
              timestamp TEXT,
              PRIMARY KEY (answer_message_id, user_id, conversation_id)
            );

            CREATE TABLE IF NOT EXISTS t_knowledge_file (
              knowledge_id TEXT NOT NULL,
              filename TEXT NOT NULL UNIQUE,
              title TEXT NOT NULL,
              file_path TEXT NOT NULL,
              size INTEGER NOT NULL DEFAULT 0,
              content_hash TEXT NOT NULL,
              preview TEXT,
              category TEXT NOT NULL DEFAULT '未分类',
              tags TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'published',
              owner TEXT,
              visibility TEXT NOT NULL DEFAULT 'internal',
              review_notes TEXT,
              published_at TEXT,
              archived_at TEXT,
              created_at TEXT,
              updated_at TEXT,
              PRIMARY KEY (knowledge_id)
            );

            CREATE TABLE IF NOT EXISTS t_knowledge_file_revision (
              revision_id TEXT NOT NULL,
              knowledge_id TEXT NOT NULL,
              filename TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              size INTEGER NOT NULL DEFAULT 0,
              content_hash TEXT NOT NULL,
              action TEXT NOT NULL DEFAULT 'save',
              status TEXT NOT NULL DEFAULT 'published',
              category TEXT NOT NULL DEFAULT '未分类',
              tags TEXT NOT NULL DEFAULT '[]',
              review_notes TEXT,
              timestamp TEXT,
              PRIMARY KEY (revision_id)
            );

            CREATE TABLE IF NOT EXISTS t_knowledge_hit (
              hit_id TEXT NOT NULL,
              channel TEXT NOT NULL,
              query TEXT NOT NULL,
              user_id TEXT,
              conversation_id TEXT,
              message_id TEXT,
              filename TEXT,
              heading TEXT,
              score REAL NOT NULL DEFAULT 0,
              status TEXT,
              timestamp TEXT,
              PRIMARY KEY (hit_id)
            );

            CREATE TABLE IF NOT EXISTS t_agent_trace (
              trace_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              query_message_id TEXT NOT NULL,
              answer_message_id TEXT NOT NULL,
              query TEXT NOT NULL,
              answer TEXT,
              status TEXT NOT NULL,
              guardrails TEXT,
              diagnostic_state TEXT,
              total_ms INTEGER NOT NULL DEFAULT 0,
              error TEXT,
              created_at TEXT,
              updated_at TEXT,
              PRIMARY KEY (trace_id)
            );

            CREATE TABLE IF NOT EXISTS t_agent_span (
              span_id TEXT NOT NULL,
              trace_id TEXT NOT NULL,
              parent_span_id TEXT,
              name TEXT NOT NULL,
              kind TEXT NOT NULL,
              input TEXT,
              output TEXT,
              status TEXT NOT NULL,
              duration_ms INTEGER NOT NULL DEFAULT 0,
              error TEXT,
              started_at TEXT,
              ended_at TEXT,
              PRIMARY KEY (span_id)
            );

            CREATE TABLE IF NOT EXISTS t_diagnostic_state (
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              current_step TEXT NOT NULL,
              summary TEXT,
              facts TEXT NOT NULL DEFAULT '[]',
              open_questions TEXT NOT NULL DEFAULT '[]',
              risk_level TEXT NOT NULL DEFAULT 'low',
              updated_at TEXT,
              PRIMARY KEY (user_id, conversation_id)
            );
            """
        )
        _ensure_column(conn, "t_knowledge_file", "category", "TEXT NOT NULL DEFAULT '未分类'")
        _ensure_column(conn, "t_knowledge_file", "tags", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "t_knowledge_file", "status", "TEXT NOT NULL DEFAULT 'published'")
        _ensure_column(conn, "t_knowledge_file", "owner", "TEXT")
        _ensure_column(conn, "t_knowledge_file", "visibility", "TEXT NOT NULL DEFAULT 'internal'")
        _ensure_column(conn, "t_knowledge_file", "review_notes", "TEXT")
        _ensure_column(conn, "t_knowledge_file", "published_at", "TEXT")
        _ensure_column(conn, "t_knowledge_file", "archived_at", "TEXT")
        _ensure_column(conn, "t_knowledge_file_revision", "action", "TEXT NOT NULL DEFAULT 'save'")
        _ensure_column(conn, "t_knowledge_file_revision", "status", "TEXT NOT NULL DEFAULT 'published'")
        _ensure_column(conn, "t_knowledge_file_revision", "category", "TEXT NOT NULL DEFAULT '未分类'")
        _ensure_column(conn, "t_knowledge_file_revision", "tags", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "t_knowledge_file_revision", "review_notes", "TEXT")
        _ensure_column(conn, "t_chat_memory", "trace_id", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def check_db(db_path: Optional[Path] = None) -> Dict[str, Any]:
    path = db_path or DB_PATH
    with connect(path) as conn:
        conn.execute("SELECT 1").fetchone()
    return {"ok": True, "path": str(path)}


def upsert_conversation(user_id: str, conversation_id: str, title: str, service: str, scene: str) -> None:
    timestamp = now_text()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_conversation(user_id, conversation_id, title, timestamp)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, conversation_id)
            DO UPDATE SET title = excluded.title, timestamp = excluded.timestamp
            """,
            (user_id, conversation_id, title, timestamp),
        )
        conn.execute(
            """
            INSERT INTO t_conversation_context(user_id, conversation_id, service, scene, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, conversation_id)
            DO UPDATE SET service = excluded.service, scene = excluded.scene, timestamp = excluded.timestamp
            """,
            (user_id, conversation_id, service, scene, timestamp),
        )


def add_chat(
    memory_id: str,
    user_id: str,
    conversation_id: str,
    message_type: str,
    content: str,
    trace_id: Optional[str] = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO t_chat_memory(memory_id, user_id, conversation_id, type, content, timestamp, trace_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, user_id, conversation_id, message_type, content, now_text(), trace_id),
        )


def find_query_message_id(answer_message_id: str, user_id: str, conversation_id: str) -> Optional[str]:
    with connect() as conn:
        answer = conn.execute(
            """
            SELECT rowid
            FROM t_chat_memory
            WHERE memory_id = ? AND user_id = ? AND conversation_id = ? AND type = 'assistant'
            """,
            (answer_message_id, user_id, conversation_id),
        ).fetchone()
        if not answer:
            return None

        query = conn.execute(
            """
            SELECT memory_id
            FROM t_chat_memory
            WHERE user_id = ? AND conversation_id = ? AND type = 'user' AND rowid < ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (user_id, conversation_id, answer["rowid"]),
        ).fetchone()
        return query["memory_id"] if query else None


def save_feedback(
    answer_message_id: str,
    user_id: str,
    conversation_id: str,
    feedback: str,
    query_message_id: Optional[str] = None,
    reason: Optional[Dict[str, Any]] = None,
) -> None:
    resolved_query_message_id = query_message_id or find_query_message_id(
        answer_message_id=answer_message_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_chat_feedback(answer_message_id, user_id, conversation_id, query_message_id, feedback, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(answer_message_id, user_id, conversation_id)
            DO UPDATE SET feedback = excluded.feedback, reason = excluded.reason, timestamp = excluded.timestamp
            """,
            (
                answer_message_id,
                user_id,
                conversation_id,
                resolved_query_message_id or "",
                feedback,
                json.dumps(reason, ensure_ascii=False) if reason is not None else None,
                now_text(),
            ),
        )


def list_conversations(user_id: str, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT user_id, conversation_id, title, timestamp FROM t_conversation WHERE user_id = ?"
    params: List[Any] = [user_id]
    if conversation_id:
        sql += " AND conversation_id = ?"
        params.append(conversation_id)
    sql += " ORDER BY timestamp DESC"
    with connect() as conn:
        return [
            {
                "userId": row["user_id"],
                "conversationId": row["conversation_id"],
                "title": row["title"],
                "timestamp": row["timestamp"],
            }
            for row in conn.execute(sql, params).fetchall()
        ]


def list_chats(user_id: str, conversation_id: str, page: int, page_size: int) -> List[Dict[str, Any]]:
    offset = (page - 1) * page_size
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT memory.memory_id AS messageId, memory.user_id AS userId,
                   memory.conversation_id AS conversationId, memory.type,
                   memory.content, memory.timestamp, memory.trace_id AS traceId,
                   feedback.feedback, feedback.reason,
                   feedback.query_message_id AS queryMessageId,
                   feedback.timestamp AS feedbackTimestamp
            FROM t_chat_memory AS memory
            LEFT JOIN t_chat_feedback AS feedback
              ON feedback.answer_message_id = memory.memory_id
             AND feedback.user_id = memory.user_id
             AND feedback.conversation_id = memory.conversation_id
            WHERE memory.user_id = ? AND memory.conversation_id = ?
            ORDER BY memory.timestamp ASC
            LIMIT ? OFFSET ?
            """,
            (user_id, conversation_id, page_size, offset),
        ).fetchall()

    result: List[Dict[str, Any]] = []
    for row in rows:
        reason = json.loads(row["reason"]) if row["reason"] else None
        query_message_id = row["queryMessageId"] if "queryMessageId" in row.keys() else None
        if row["type"] == "assistant" and not query_message_id:
            query_message_id = find_query_message_id(row["messageId"], row["userId"], row["conversationId"])
        result.append(
            {
                "messageId": row["messageId"],
                "queryMessageId": query_message_id,
                "userId": row["userId"],
                "conversationId": row["conversationId"],
                "type": row["type"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "traceId": row["traceId"],
                "feedbackInfo": {
                    "feedback": row["feedback"],
                    "reason": reason,
                    "timestamp": row["feedbackTimestamp"],
                },
            }
        )
    return result


def save_agent_trace(trace: Dict[str, Any], spans: List[Dict[str, Any]]) -> None:
    timestamp = now_text()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_agent_trace(
              trace_id, user_id, conversation_id, query_message_id, answer_message_id,
              query, answer, status, guardrails, diagnostic_state, total_ms, error,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trace_id)
            DO UPDATE SET
              answer = excluded.answer,
              status = excluded.status,
              guardrails = excluded.guardrails,
              diagnostic_state = excluded.diagnostic_state,
              total_ms = excluded.total_ms,
              error = excluded.error,
              updated_at = excluded.updated_at
            """,
            (
                trace["traceId"],
                trace["userId"],
                trace["conversationId"],
                trace["queryMessageId"],
                trace["answerMessageId"],
                trace["query"],
                trace.get("answer"),
                trace.get("status", "ok"),
                json.dumps(trace.get("guardrails", []), ensure_ascii=False),
                json.dumps(trace.get("diagnosticState", {}), ensure_ascii=False),
                int(trace.get("totalMs") or 0),
                trace.get("error"),
                trace.get("createdAt") or timestamp,
                timestamp,
            ),
        )
        conn.execute("DELETE FROM t_agent_span WHERE trace_id = ?", (trace["traceId"],))
        for span in spans:
            conn.execute(
                """
                INSERT INTO t_agent_span(
                  span_id, trace_id, parent_span_id, name, kind, input, output,
                  status, duration_ms, error, started_at, ended_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span["spanId"],
                    trace["traceId"],
                    span.get("parentSpanId"),
                    span["name"],
                    span["kind"],
                    json.dumps(span.get("input"), ensure_ascii=False),
                    json.dumps(span.get("output"), ensure_ascii=False),
                    span.get("status", "ok"),
                    int(span.get("durationMs") or 0),
                    span.get("error"),
                    span.get("startedAt"),
                    span.get("endedAt"),
                ),
            )


def get_agent_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        trace = conn.execute(
            """
            SELECT trace_id, user_id, conversation_id, query_message_id, answer_message_id,
                   query, answer, status, guardrails, diagnostic_state, total_ms, error,
                   created_at, updated_at
            FROM t_agent_trace
            WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()
        if not trace:
            return None
        spans = conn.execute(
            """
            SELECT span_id, trace_id, parent_span_id, name, kind, input, output,
                   status, duration_ms, error, started_at, ended_at
            FROM t_agent_span
            WHERE trace_id = ?
            ORDER BY started_at ASC, rowid ASC
            """,
            (trace_id,),
        ).fetchall()
    return {
        "traceId": trace["trace_id"],
        "userId": trace["user_id"],
        "conversationId": trace["conversation_id"],
        "queryMessageId": trace["query_message_id"],
        "answerMessageId": trace["answer_message_id"],
        "query": trace["query"],
        "answer": trace["answer"],
        "status": trace["status"],
        "guardrails": json.loads(trace["guardrails"] or "[]"),
        "diagnosticState": json.loads(trace["diagnostic_state"] or "{}"),
        "totalMs": trace["total_ms"],
        "error": trace["error"],
        "createdAt": trace["created_at"],
        "updatedAt": trace["updated_at"],
        "spans": [
            {
                "spanId": row["span_id"],
                "traceId": row["trace_id"],
                "parentSpanId": row["parent_span_id"],
                "name": row["name"],
                "kind": row["kind"],
                "input": json.loads(row["input"] or "null"),
                "output": json.loads(row["output"] or "null"),
                "status": row["status"],
                "durationMs": row["duration_ms"],
                "error": row["error"],
                "startedAt": row["started_at"],
                "endedAt": row["ended_at"],
            }
            for row in spans
        ],
    }


def get_diagnostic_state(user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, conversation_id, current_step, summary, facts, open_questions, risk_level, updated_at
            FROM t_diagnostic_state
            WHERE user_id = ? AND conversation_id = ?
            """,
            (user_id, conversation_id),
        ).fetchone()
    if not row:
        return None
    return {
        "userId": row["user_id"],
        "conversationId": row["conversation_id"],
        "currentStep": row["current_step"],
        "summary": row["summary"],
        "facts": json.loads(row["facts"] or "[]"),
        "openQuestions": json.loads(row["open_questions"] or "[]"),
        "riskLevel": row["risk_level"],
        "updatedAt": row["updated_at"],
    }


def upsert_diagnostic_state(
    user_id: str,
    conversation_id: str,
    current_step: str,
    summary: str,
    facts: List[str],
    open_questions: List[str],
    risk_level: str,
) -> Dict[str, Any]:
    timestamp = now_text()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_diagnostic_state(
              user_id, conversation_id, current_step, summary, facts, open_questions, risk_level, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, conversation_id)
            DO UPDATE SET
              current_step = excluded.current_step,
              summary = excluded.summary,
              facts = excluded.facts,
              open_questions = excluded.open_questions,
              risk_level = excluded.risk_level,
              updated_at = excluded.updated_at
            """,
            (
                user_id,
                conversation_id,
                current_step,
                summary,
                json.dumps(facts, ensure_ascii=False),
                json.dumps(open_questions, ensure_ascii=False),
                risk_level,
                timestamp,
            ),
        )
    return get_diagnostic_state(user_id, conversation_id) or {}


def upsert_knowledge_file(
    filename: str,
    title: str,
    file_path: str,
    content: str,
    content_hash: str,
    size: int,
    preview: str,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    visibility: Optional[str] = None,
    review_notes: Optional[str] = None,
    create_revision: bool = True,
    timestamp: Optional[str] = None,
    action: str = "save",
) -> Dict[str, Any]:
    effective_timestamp = timestamp or now_text()
    normalized_tags = json.dumps(tags or [], ensure_ascii=False)
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT knowledge_id, created_at, updated_at, content_hash, category, tags, status,
                   owner, visibility, review_notes, published_at, archived_at
            FROM t_knowledge_file
            WHERE filename = ?
            """,
            (filename,),
        ).fetchone()
        knowledge_id = existing["knowledge_id"] if existing else str(uuid.uuid4())
        created_at = existing["created_at"] if existing else effective_timestamp
        effective_category = category or (existing["category"] if existing else "未分类")
        effective_tags = normalized_tags if tags is not None else (existing["tags"] if existing else "[]")
        effective_status = status or (existing["status"] if existing else "published")
        effective_owner = owner if owner is not None else (existing["owner"] if existing else None)
        effective_visibility = visibility or (existing["visibility"] if existing else "internal")
        effective_review_notes = review_notes if review_notes is not None else (existing["review_notes"] if existing else None)
        content_changed = not existing or existing["content_hash"] != content_hash
        updated_at = effective_timestamp if (create_revision or content_changed) else existing["updated_at"]
        published_at = existing["published_at"] if existing else None
        archived_at = existing["archived_at"] if existing else None
        if effective_status == "published" and not published_at:
            published_at = effective_timestamp
        if effective_status == "archived" and not archived_at:
            archived_at = effective_timestamp
        if effective_status != "archived":
            archived_at = None

        conn.execute(
            """
            INSERT INTO t_knowledge_file(
              knowledge_id, filename, title, file_path, size, content_hash, preview,
              category, tags, status, owner, visibility, review_notes, published_at, archived_at,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename)
            DO UPDATE SET
              title = excluded.title,
              file_path = excluded.file_path,
              size = excluded.size,
              content_hash = excluded.content_hash,
              preview = excluded.preview,
              category = excluded.category,
              tags = excluded.tags,
              status = excluded.status,
              owner = excluded.owner,
              visibility = excluded.visibility,
              review_notes = excluded.review_notes,
              published_at = excluded.published_at,
              archived_at = excluded.archived_at,
              updated_at = excluded.updated_at
            """,
            (
                knowledge_id,
                filename,
                title,
                file_path,
                size,
                content_hash,
                preview,
                effective_category,
                effective_tags,
                effective_status,
                effective_owner,
                effective_visibility,
                effective_review_notes,
                published_at,
                archived_at,
                created_at,
                updated_at,
            ),
        )

        if create_revision and (content_changed or action != "save"):
            conn.execute(
                """
                INSERT INTO t_knowledge_file_revision(
                  revision_id, knowledge_id, filename, title, content, size, content_hash,
                  action, status, category, tags, review_notes, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    knowledge_id,
                    filename,
                    title,
                    content,
                    size,
                    content_hash,
                    action,
                    effective_status,
                    effective_category,
                    effective_tags,
                    effective_review_notes,
                    effective_timestamp,
                ),
            )

    return {
        "knowledgeId": knowledge_id,
        "filename": filename,
        "title": title,
        "filePath": file_path,
        "size": size,
        "contentHash": content_hash,
        "preview": preview,
        "category": effective_category,
        "tags": json.loads(effective_tags) if effective_tags else [],
        "status": effective_status,
        "owner": effective_owner,
        "visibility": effective_visibility,
        "reviewNotes": effective_review_notes,
        "publishedAt": published_at,
        "archivedAt": archived_at,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def list_knowledge_files() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT knowledge_id, filename, title, file_path, size, content_hash, preview,
                   category, tags, status, owner, visibility, review_notes, published_at, archived_at,
                   created_at, updated_at
            FROM t_knowledge_file
            ORDER BY
              CASE status WHEN 'review' THEN 0 WHEN 'draft' THEN 1 WHEN 'published' THEN 2 ELSE 3 END,
              updated_at DESC,
              filename ASC
            """
        ).fetchall()
    return [
        {
            "knowledgeId": row["knowledge_id"],
            "filename": row["filename"],
            "title": row["title"],
            "filePath": row["file_path"],
            "size": row["size"],
            "contentHash": row["content_hash"],
            "preview": row["preview"],
            "category": row["category"],
            "tags": json.loads(row["tags"] or "[]"),
            "status": row["status"],
            "owner": row["owner"],
            "visibility": row["visibility"],
            "reviewNotes": row["review_notes"],
            "publishedAt": row["published_at"],
            "archivedAt": row["archived_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


def get_knowledge_file(filename: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT knowledge_id, filename, title, file_path, size, content_hash, preview,
                   category, tags, status, owner, visibility, review_notes, published_at, archived_at,
                   created_at, updated_at
            FROM t_knowledge_file
            WHERE filename = ?
            """,
            (filename,),
        ).fetchone()
    if not row:
        return None
    return {
        "knowledgeId": row["knowledge_id"],
        "filename": row["filename"],
        "title": row["title"],
        "filePath": row["file_path"],
        "size": row["size"],
        "contentHash": row["content_hash"],
        "preview": row["preview"],
        "category": row["category"],
        "tags": json.loads(row["tags"] or "[]"),
        "status": row["status"],
        "owner": row["owner"],
        "visibility": row["visibility"],
        "reviewNotes": row["review_notes"],
        "publishedAt": row["published_at"],
        "archivedAt": row["archived_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def list_knowledge_revisions(filename: Optional[str] = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    offset = (page - 1) * page_size
    params: List[Any] = []
    where = ""
    if filename:
        where = "WHERE filename = ?"
        params.append(filename)
    params.extend([page_size, offset])
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT revision_id, knowledge_id, filename, title, content, size, content_hash,
                   action, status, category, tags, review_notes, timestamp
            FROM t_knowledge_file_revision
            {where}
            ORDER BY timestamp DESC, rowid DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
    return [
        {
            "revisionId": row["revision_id"],
            "knowledgeId": row["knowledge_id"],
            "filename": row["filename"],
            "title": row["title"],
            "content": row["content"],
            "size": row["size"],
            "contentHash": row["content_hash"],
            "action": row["action"],
            "status": row["status"],
            "category": row["category"],
            "tags": json.loads(row["tags"] or "[]"),
            "reviewNotes": row["review_notes"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def update_knowledge_status(filename: str, status: str, review_notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    allowed_statuses = {"draft", "review", "published", "archived"}
    if status not in allowed_statuses:
        raise ValueError(f"Unsupported knowledge status: {status}")

    timestamp = now_text()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT knowledge_id, filename, title, file_path, size, content_hash, preview,
                   category, tags, status, owner, visibility, review_notes, published_at, archived_at
            FROM t_knowledge_file
            WHERE filename = ?
            """,
            (filename,),
        ).fetchone()
        if not row:
            return None

        published_at = row["published_at"]
        archived_at = row["archived_at"]
        if status == "published":
            published_at = timestamp
            archived_at = None
        elif status == "archived":
            archived_at = timestamp
        else:
            archived_at = None

        effective_notes = review_notes if review_notes is not None else row["review_notes"]
        conn.execute(
            """
            UPDATE t_knowledge_file
            SET status = ?, review_notes = ?, published_at = ?, archived_at = ?, updated_at = ?
            WHERE filename = ?
            """,
            (status, effective_notes, published_at, archived_at, timestamp, filename),
        )
        conn.execute(
            """
            INSERT INTO t_knowledge_file_revision(
              revision_id, knowledge_id, filename, title, content, size, content_hash,
              action, status, category, tags, review_notes, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                row["knowledge_id"],
                row["filename"],
                row["title"],
                Path(row["file_path"]).read_text(encoding="utf-8") if Path(row["file_path"]).exists() else "",
                row["size"],
                row["content_hash"],
                f"status:{status}",
                status,
                row["category"],
                row["tags"],
                effective_notes,
                timestamp,
            ),
        )
    return get_knowledge_file(filename)


def record_knowledge_hits(
    channel: str,
    query: str,
    results: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> None:
    if not results:
        return
    timestamp = now_text()
    with connect() as conn:
        for item in results:
            filename = Path(item.get("source", "")).name
            status = None
            if filename:
                row = conn.execute("SELECT status FROM t_knowledge_file WHERE filename = ?", (filename,)).fetchone()
                status = row["status"] if row else None
            conn.execute(
                """
                INSERT INTO t_knowledge_hit(
                  hit_id, channel, query, user_id, conversation_id, message_id,
                  filename, heading, score, status, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    channel,
                    query,
                    user_id,
                    conversation_id,
                    message_id,
                    filename,
                    item.get("heading"),
                    float(item.get("score") or 0),
                    status,
                    timestamp,
                ),
            )


def list_knowledge_gaps(page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    offset = (page - 1) * page_size
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
              feedback.user_id,
              feedback.conversation_id,
              feedback.answer_message_id,
              feedback.query_message_id,
              feedback.reason,
              feedback.timestamp,
              query.content AS query_content,
              MAX(hit.score) AS best_score,
              COUNT(hit.hit_id) AS hit_count
            FROM t_chat_feedback AS feedback
            LEFT JOIN t_chat_memory AS query
              ON query.memory_id = feedback.query_message_id
             AND query.user_id = feedback.user_id
             AND query.conversation_id = feedback.conversation_id
            LEFT JOIN t_knowledge_hit AS hit
              ON hit.query = query.content
             AND hit.status = 'published'
            WHERE feedback.feedback = 'unlike'
            GROUP BY feedback.answer_message_id, feedback.user_id, feedback.conversation_id
            HAVING hit_count = 0 OR best_score < 0.18
            ORDER BY feedback.timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "userId": row["user_id"],
                "conversationId": row["conversation_id"],
                "answerMessageId": row["answer_message_id"],
                "queryMessageId": row["query_message_id"],
                "query": row["query_content"] or "",
                "reason": json.loads(row["reason"]) if row["reason"] else None,
                "bestScore": round(float(row["best_score"] or 0), 4),
                "hitCount": row["hit_count"],
                "timestamp": row["timestamp"],
            }
        )
    return result


def _date_range(start_date: str, end_date: str) -> List[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if end < start:
        start, end = end, start
    days = (end - start).days
    return [(start + timedelta(days=index)).isoformat() for index in range(days + 1)]


def _ops_filters(
    table_alias: str,
    start_date: str,
    end_date: str,
    user_id: Optional[str],
    service: Optional[str],
    scene: Optional[str],
) -> tuple[str, List[Any]]:
    where = [f"date({table_alias}.timestamp) BETWEEN ? AND ?"]
    params: List[Any] = [start_date, end_date]
    if user_id:
        where.append(f"{table_alias}.user_id = ?")
        params.append(user_id)
    if service:
        where.append("ctx.service = ?")
        params.append(service)
    if scene:
        where.append("ctx.scene = ?")
        params.append(scene)
    return " AND ".join(where), params


def get_ops_dashboard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    service: Optional[str] = None,
    scene: Optional[str] = None,
) -> Dict[str, Any]:
    effective_start = start_date or default_start_date_text()
    effective_end = end_date or today_text()
    days = _date_range(effective_start, effective_end)

    chat_where, chat_params = _ops_filters("m", effective_start, effective_end, user_id, service, scene)
    feedback_where, feedback_params = _ops_filters("f", effective_start, effective_end, user_id, service, scene)

    daily = {
        day: {
            "date": day,
            "activeUsers": 0,
            "conversationCount": 0,
            "questionCount": 0,
            "assistantReplyCount": 0,
            "likeCount": 0,
            "unlikeCount": 0,
            "feedbackCount": 0,
        }
        for day in days
    }
    top_users: Dict[str, Dict[str, Any]] = {}
    reason_counts: Dict[str, int] = {}

    with connect() as conn:
        chat_summary = conn.execute(
            f"""
            SELECT
              COUNT(DISTINCT CASE WHEN m.type = 'user' THEN m.user_id END) AS active_users,
              COUNT(DISTINCT CASE WHEN m.type = 'user' THEN m.user_id || ':' || m.conversation_id END) AS conversation_count,
              SUM(CASE WHEN m.type = 'user' THEN 1 ELSE 0 END) AS question_count,
              SUM(CASE WHEN m.type = 'assistant' THEN 1 ELSE 0 END) AS assistant_reply_count
            FROM t_chat_memory AS m
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = m.user_id AND ctx.conversation_id = m.conversation_id
            WHERE {chat_where}
            """,
            chat_params,
        ).fetchone()

        feedback_summary = conn.execute(
            f"""
            SELECT
              SUM(CASE WHEN f.feedback = 'like' THEN 1 ELSE 0 END) AS like_count,
              SUM(CASE WHEN f.feedback = 'unlike' THEN 1 ELSE 0 END) AS unlike_count,
              SUM(CASE WHEN f.feedback IN ('like', 'unlike') THEN 1 ELSE 0 END) AS feedback_count
            FROM t_chat_feedback AS f
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = f.user_id AND ctx.conversation_id = f.conversation_id
            WHERE {feedback_where}
            """,
            feedback_params,
        ).fetchone()

        chat_daily_rows = conn.execute(
            f"""
            SELECT
              date(m.timestamp) AS metric_date,
              COUNT(DISTINCT CASE WHEN m.type = 'user' THEN m.user_id END) AS active_users,
              COUNT(DISTINCT CASE WHEN m.type = 'user' THEN m.user_id || ':' || m.conversation_id END) AS conversation_count,
              SUM(CASE WHEN m.type = 'user' THEN 1 ELSE 0 END) AS question_count,
              SUM(CASE WHEN m.type = 'assistant' THEN 1 ELSE 0 END) AS assistant_reply_count
            FROM t_chat_memory AS m
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = m.user_id AND ctx.conversation_id = m.conversation_id
            WHERE {chat_where}
            GROUP BY date(m.timestamp)
            ORDER BY metric_date ASC
            """,
            chat_params,
        ).fetchall()

        feedback_daily_rows = conn.execute(
            f"""
            SELECT
              date(f.timestamp) AS metric_date,
              SUM(CASE WHEN f.feedback = 'like' THEN 1 ELSE 0 END) AS like_count,
              SUM(CASE WHEN f.feedback = 'unlike' THEN 1 ELSE 0 END) AS unlike_count,
              SUM(CASE WHEN f.feedback IN ('like', 'unlike') THEN 1 ELSE 0 END) AS feedback_count
            FROM t_chat_feedback AS f
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = f.user_id AND ctx.conversation_id = f.conversation_id
            WHERE {feedback_where}
            GROUP BY date(f.timestamp)
            ORDER BY metric_date ASC
            """,
            feedback_params,
        ).fetchall()

        user_rows = conn.execute(
            f"""
            SELECT
              m.user_id,
              COUNT(*) AS question_count,
              COUNT(DISTINCT m.conversation_id) AS conversation_count,
              MAX(m.timestamp) AS last_active_at
            FROM t_chat_memory AS m
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = m.user_id AND ctx.conversation_id = m.conversation_id
            WHERE {chat_where} AND m.type = 'user'
            GROUP BY m.user_id
            ORDER BY question_count DESC, last_active_at DESC
            LIMIT 10
            """,
            chat_params,
        ).fetchall()

        user_feedback_rows = conn.execute(
            f"""
            SELECT
              f.user_id,
              SUM(CASE WHEN f.feedback = 'like' THEN 1 ELSE 0 END) AS like_count,
              SUM(CASE WHEN f.feedback = 'unlike' THEN 1 ELSE 0 END) AS unlike_count
            FROM t_chat_feedback AS f
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = f.user_id AND ctx.conversation_id = f.conversation_id
            WHERE {feedback_where}
            GROUP BY f.user_id
            """,
            feedback_params,
        ).fetchall()

        unlike_rows = conn.execute(
            f"""
            SELECT
              f.user_id, f.conversation_id, f.answer_message_id, f.query_message_id,
              f.reason, f.timestamp, ctx.service, ctx.scene,
              query.content AS query_content,
              answer.content AS answer_content
            FROM t_chat_feedback AS f
            LEFT JOIN t_conversation_context AS ctx
              ON ctx.user_id = f.user_id AND ctx.conversation_id = f.conversation_id
            LEFT JOIN t_chat_memory AS query
              ON query.memory_id = f.query_message_id
             AND query.user_id = f.user_id
             AND query.conversation_id = f.conversation_id
            LEFT JOIN t_chat_memory AS answer
              ON answer.memory_id = f.answer_message_id
             AND answer.user_id = f.user_id
             AND answer.conversation_id = f.conversation_id
            WHERE {feedback_where} AND f.feedback = 'unlike'
            ORDER BY f.timestamp DESC
            LIMIT 20
            """,
            feedback_params,
        ).fetchall()

    for row in chat_daily_rows:
        item = daily.get(row["metric_date"])
        if item:
            item["activeUsers"] = row["active_users"] or 0
            item["conversationCount"] = row["conversation_count"] or 0
            item["questionCount"] = row["question_count"] or 0
            item["assistantReplyCount"] = row["assistant_reply_count"] or 0

    for row in feedback_daily_rows:
        item = daily.get(row["metric_date"])
        if item:
            item["likeCount"] = row["like_count"] or 0
            item["unlikeCount"] = row["unlike_count"] or 0
            item["feedbackCount"] = row["feedback_count"] or 0

    for row in user_rows:
        top_users[row["user_id"]] = {
            "userId": row["user_id"],
            "questionCount": row["question_count"] or 0,
            "conversationCount": row["conversation_count"] or 0,
            "likeCount": 0,
            "unlikeCount": 0,
            "lastActiveAt": row["last_active_at"],
        }

    for row in user_feedback_rows:
        user = top_users.setdefault(
            row["user_id"],
            {
                "userId": row["user_id"],
                "questionCount": 0,
                "conversationCount": 0,
                "likeCount": 0,
                "unlikeCount": 0,
                "lastActiveAt": None,
            },
        )
        user["likeCount"] = row["like_count"] or 0
        user["unlikeCount"] = row["unlike_count"] or 0

    recent_unlikes = []
    for row in unlike_rows:
        reason = json.loads(row["reason"]) if row["reason"] else {}
        for reason_type in reason.get("feedbackInfoTypes") or []:
            reason_counts[reason_type] = reason_counts.get(reason_type, 0) + 1
        feedback_text = reason.get("feedbackInfo")
        if feedback_text:
            reason_counts[feedback_text] = reason_counts.get(feedback_text, 0) + 1
        recent_unlikes.append(
            {
                "userId": row["user_id"],
                "conversationId": row["conversation_id"],
                "answerMessageId": row["answer_message_id"],
                "queryMessageId": row["query_message_id"],
                "service": row["service"],
                "scene": row["scene"],
                "query": row["query_content"] or "",
                "answerPreview": (row["answer_content"] or "")[:180],
                "reason": reason,
                "timestamp": row["timestamp"],
            }
        )

    question_count = (chat_summary["question_count"] if chat_summary else 0) or 0
    assistant_reply_count = (chat_summary["assistant_reply_count"] if chat_summary else 0) or 0
    feedback_count = (feedback_summary["feedback_count"] if feedback_summary else 0) or 0
    unlike_count = (feedback_summary["unlike_count"] if feedback_summary else 0) or 0
    summary = {
        "activeUsers": (chat_summary["active_users"] if chat_summary else 0) or 0,
        "conversationCount": (chat_summary["conversation_count"] if chat_summary else 0) or 0,
        "questionCount": question_count,
        "assistantReplyCount": assistant_reply_count,
        "likeCount": (feedback_summary["like_count"] if feedback_summary else 0) or 0,
        "unlikeCount": unlike_count,
        "feedbackCount": feedback_count,
        "feedbackRate": round(feedback_count / assistant_reply_count, 4) if assistant_reply_count else 0,
        "unlikeRate": round(unlike_count / feedback_count, 4) if feedback_count else 0,
    }

    return {
        "range": {"startDate": days[0], "endDate": days[-1]},
        "filters": {"userId": user_id, "service": service, "scene": scene},
        "summary": summary,
        "daily": list(daily.values()),
        "reasonTop": [
            {"reason": key, "count": value}
            for key, value in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)[:10]
        ],
        "recentUnlikes": recent_unlikes,
        "topUsers": sorted(
            top_users.values(),
            key=lambda item: (item["questionCount"], item["unlikeCount"], item["likeCount"]),
            reverse=True,
        )[:10],
    }
