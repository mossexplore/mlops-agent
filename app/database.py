import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DB_PATH = Path(os.environ.get("WISE_AGENT_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "agent.db"))


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
              timestamp TEXT,
              PRIMARY KEY (revision_id)
            );
            """
        )


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


def add_chat(memory_id: str, user_id: str, conversation_id: str, message_type: str, content: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO t_chat_memory(memory_id, user_id, conversation_id, type, content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (memory_id, user_id, conversation_id, message_type, content, now_text()),
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
                   memory.content, memory.timestamp,
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
                "feedbackInfo": {
                    "feedback": row["feedback"],
                    "reason": reason,
                    "timestamp": row["feedbackTimestamp"],
                },
            }
        )
    return result


def upsert_knowledge_file(
    filename: str,
    title: str,
    file_path: str,
    content: str,
    content_hash: str,
    size: int,
    preview: str,
    create_revision: bool = True,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    effective_timestamp = timestamp or now_text()
    with connect() as conn:
        existing = conn.execute(
            "SELECT knowledge_id, created_at, updated_at, content_hash FROM t_knowledge_file WHERE filename = ?",
            (filename,),
        ).fetchone()
        knowledge_id = existing["knowledge_id"] if existing else str(uuid.uuid4())
        created_at = existing["created_at"] if existing else effective_timestamp
        content_changed = not existing or existing["content_hash"] != content_hash
        updated_at = effective_timestamp if (create_revision or content_changed) else existing["updated_at"]

        conn.execute(
            """
            INSERT INTO t_knowledge_file(
              knowledge_id, filename, title, file_path, size, content_hash, preview, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename)
            DO UPDATE SET
              title = excluded.title,
              file_path = excluded.file_path,
              size = excluded.size,
              content_hash = excluded.content_hash,
              preview = excluded.preview,
              updated_at = excluded.updated_at
            """,
            (knowledge_id, filename, title, file_path, size, content_hash, preview, created_at, updated_at),
        )

        if create_revision and content_changed:
            conn.execute(
                """
                INSERT INTO t_knowledge_file_revision(
                  revision_id, knowledge_id, filename, title, content, size, content_hash, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), knowledge_id, filename, title, content, size, content_hash, effective_timestamp),
            )

    return {
        "knowledgeId": knowledge_id,
        "filename": filename,
        "title": title,
        "filePath": file_path,
        "size": size,
        "contentHash": content_hash,
        "preview": preview,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def list_knowledge_files() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT knowledge_id, filename, title, file_path, size, content_hash, preview, created_at, updated_at
            FROM t_knowledge_file
            ORDER BY updated_at DESC, filename ASC
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
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


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
            SELECT revision_id, knowledge_id, filename, title, content, size, content_hash, timestamp
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
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]
