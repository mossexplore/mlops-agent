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


def safe_json_loads(value: Optional[str], default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


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

            CREATE TABLE IF NOT EXISTS t_feedback_review (
              answer_message_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              quality_reason TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'open',
              annotation TEXT,
              reviewer TEXT,
              eval_case_id TEXT,
              updated_at TEXT,
              PRIMARY KEY (answer_message_id, user_id, conversation_id)
            );

            CREATE TABLE IF NOT EXISTS t_eval_case (
              case_id TEXT NOT NULL,
              title TEXT NOT NULL,
              query TEXT NOT NULL,
              expected_answer TEXT,
              required_steps TEXT NOT NULL DEFAULT '[]',
              forbidden_content TEXT NOT NULL DEFAULT '[]',
              tags TEXT NOT NULL DEFAULT '[]',
              source_feedback_id TEXT,
              status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT,
              updated_at TEXT,
              PRIMARY KEY (case_id)
            );

            CREATE TABLE IF NOT EXISTS t_eval_run (
              run_id TEXT NOT NULL,
              name TEXT NOT NULL,
              variant TEXT NOT NULL,
              prompt_version TEXT,
              retrieval_threshold REAL,
              model TEXT,
              case_count INTEGER NOT NULL DEFAULT 0,
              pass_count INTEGER NOT NULL DEFAULT 0,
              avg_score REAL NOT NULL DEFAULT 0,
              knowledge_hit_rate REAL NOT NULL DEFAULT 0,
              created_at TEXT,
              PRIMARY KEY (run_id)
            );

            CREATE TABLE IF NOT EXISTS t_eval_result (
              result_id TEXT NOT NULL,
              run_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              answer TEXT,
              score REAL NOT NULL DEFAULT 0,
              passed INTEGER NOT NULL DEFAULT 0,
              checks TEXT NOT NULL DEFAULT '{}',
              knowledge_hit INTEGER NOT NULL DEFAULT 0,
              error TEXT,
              total_ms INTEGER NOT NULL DEFAULT 0,
              created_at TEXT,
              PRIMARY KEY (result_id)
            );

            CREATE TABLE IF NOT EXISTS t_ab_experiment (
              experiment_id TEXT NOT NULL,
              name TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'draft',
              variants TEXT NOT NULL DEFAULT '[]',
              traffic_split TEXT NOT NULL DEFAULT '{}',
              primary_metric TEXT NOT NULL DEFAULT 'satisfactionRate',
              notes TEXT,
              created_at TEXT,
              updated_at TEXT,
              PRIMARY KEY (experiment_id)
            );

            CREATE TABLE IF NOT EXISTS t_runbook (
              runbook_id TEXT NOT NULL,
              title TEXT NOT NULL,
              service TEXT NOT NULL DEFAULT 'Wise',
              scenario TEXT NOT NULL DEFAULT '模型任务',
              severity TEXT NOT NULL DEFAULT 'P2',
              status TEXT NOT NULL DEFAULT 'published',
              owner TEXT,
              version TEXT NOT NULL DEFAULT 'v1',
              trigger TEXT,
              summary TEXT,
              verification TEXT,
              escalation TEXT,
              risk_controls TEXT NOT NULL DEFAULT '[]',
              tags TEXT NOT NULL DEFAULT '[]',
              related_knowledge TEXT NOT NULL DEFAULT '[]',
              created_at TEXT,
              updated_at TEXT,
              PRIMARY KEY (runbook_id)
            );

            CREATE TABLE IF NOT EXISTS t_runbook_step (
              step_id TEXT NOT NULL,
              runbook_id TEXT NOT NULL,
              step_order INTEGER NOT NULL DEFAULT 1,
              title TEXT NOT NULL,
              action_type TEXT NOT NULL DEFAULT 'check',
              instruction TEXT NOT NULL,
              evidence_required TEXT,
              tool_name TEXT,
              expected_result TEXT,
              risk_level TEXT NOT NULL DEFAULT 'low',
              PRIMARY KEY (step_id)
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
        seed_sample_runbooks(conn)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_sample_runbooks(conn: sqlite3.Connection) -> None:
    timestamp = now_text()
    samples = [
        {
            "runbookId": "rb-memory-1401027",
            "title": "1401027 insufficient memory 训练任务诊断",
            "service": "Wise",
            "scenario": "模型任务",
            "severity": "P2",
            "status": "published",
            "owner": "训练平台值班",
            "version": "v1",
            "trigger": "训练任务日志出现 1401027、insufficient memory、OOMKilled 或用户反馈显存/内存不足。",
            "summary": "先确认是否真实 OOM，再区分资源规格不足、batch 配置过大、数据预处理峰值或 checkpoint 加载峰值。",
            "verification": "小样本复现通过，内存峰值低于 limit 80%，同配置任务连续两次启动成功。",
            "escalation": "若多个用户同队列集中 OOM 或节点资源异常，升级给 Wise 平台 SRE。",
            "riskControls": ["扩容、重启、终止任务前必须确认影响范围", "不能编造平台实时日志或指标"],
            "tags": ["OOM", "Memory", "1401027", "训练任务"],
            "relatedKnowledge": ["resource-oom.md"],
            "steps": [
                {
                    "title": "确认任务和失败时间",
                    "actionType": "check",
                    "instruction": "记录任务 ID、实例 ID、失败时间点和最近一次配置变更。",
                    "evidenceRequired": "任务 ID、失败时间、用户提交参数",
                    "toolName": "task_status",
                    "expectedResult": "可以定位到唯一失败实例。",
                    "riskLevel": "low",
                },
                {
                    "title": "检查 OOM 事件和资源峰值",
                    "actionType": "tool",
                    "instruction": "查询容器事件、memory limit/request、内存峰值和节点剩余资源。",
                    "evidenceRequired": "OOMKilled 事件、memory peak、limit/request",
                    "toolName": "resource_metrics",
                    "expectedResult": "判断是否超过容器限制或节点资源不足。",
                    "riskLevel": "low",
                },
                {
                    "title": "压低内存峰值后复现",
                    "actionType": "manual",
                    "instruction": "降低 batch size、num_workers、prefetch factor，关闭不必要缓存后用小样本复现。",
                    "evidenceRequired": "复现配置和运行结果",
                    "toolName": "",
                    "expectedResult": "若复现成功，说明主要是任务侧峰值配置问题。",
                    "riskLevel": "medium",
                },
                {
                    "title": "确认后再调整规格",
                    "actionType": "confirm",
                    "instruction": "只有证据表明资源规格不足时，才申请扩容或调整资源规格。",
                    "evidenceRequired": "资源峰值趋势和负责人确认",
                    "toolName": "",
                    "expectedResult": "扩容动作有审批和回退方案。",
                    "riskLevel": "high",
                },
            ],
        },
        {
            "runbookId": "rb-scheduling-pending",
            "title": "训练任务 Pending / 调度失败诊断",
            "service": "MTP",
            "scenario": "调度队列",
            "severity": "P2",
            "status": "published",
            "owner": "调度平台值班",
            "version": "v1",
            "trigger": "任务长时间 Pending、队列无资源、节点标签不匹配或调度器拒绝。",
            "summary": "按队列配额、request/limit、节点标签/污点、镜像拉取和调度事件顺序排查。",
            "verification": "任务进入 Running，调度事件无新的拒绝原因，队列水位恢复正常。",
            "escalation": "队列整体阻塞超过 15 分钟或 P1 任务受影响时升级调度负责人。",
            "riskControls": ["禁止直接抢占其他用户资源", "调整队列配额需负责人确认"],
            "tags": ["Pending", "Quota", "Scheduler", "队列"],
            "relatedKnowledge": ["scheduling-pending.md"],
            "steps": [
                {
                    "title": "读取调度事件",
                    "actionType": "tool",
                    "instruction": "查询任务 Pending 事件、调度器拒绝原因和队列水位。",
                    "evidenceRequired": "调度事件、队列配额、任务 request",
                    "toolName": "scheduling_events",
                    "expectedResult": "得到明确的拒绝原因或资源等待原因。",
                    "riskLevel": "low",
                },
                {
                    "title": "核对资源申请",
                    "actionType": "check",
                    "instruction": "确认 CPU/GPU/Memory request 是否超过队列或单节点可用资源。",
                    "evidenceRequired": "资源 request/limit 和节点可用资源",
                    "toolName": "resource_metrics",
                    "expectedResult": "判断是否为任务规格过大。",
                    "riskLevel": "low",
                },
                {
                    "title": "确认节点选择条件",
                    "actionType": "check",
                    "instruction": "检查 nodeSelector、affinity、taints/tolerations 和 GPU 型号约束。",
                    "evidenceRequired": "任务调度配置和节点标签",
                    "toolName": "task_status",
                    "expectedResult": "确认是否存在标签或污点不匹配。",
                    "riskLevel": "low",
                },
                {
                    "title": "升级或调整队列",
                    "actionType": "confirm",
                    "instruction": "若确认为队列资源不足，提交配额调整或业务排队建议。",
                    "evidenceRequired": "队列水位、影响用户、负责人确认",
                    "toolName": "",
                    "expectedResult": "配额调整有审批记录。",
                    "riskLevel": "high",
                },
            ],
        },
        {
            "runbookId": "rb-image-runtime",
            "title": "镜像 / CUDA / 依赖启动失败诊断",
            "service": "MEP",
            "scenario": "运行环境",
            "severity": "P3",
            "status": "draft",
            "owner": "镜像平台值班",
            "version": "v0.1",
            "trigger": "任务启动阶段出现 ImportError、CUDA mismatch、镜像拉取失败或依赖版本不兼容。",
            "summary": "对比成功任务与失败任务的镜像 digest、CUDA/驱动、启动命令和依赖包版本。",
            "verification": "固定镜像 digest 后小样本启动成功，关键依赖版本与基线一致。",
            "escalation": "基础镜像批量失败时升级镜像平台负责人。",
            "riskControls": ["生产镜像回滚需确认影响范围", "不要使用 latest 作为长期修复"],
            "tags": ["Image", "CUDA", "Dependency"],
            "relatedKnowledge": ["runtime-image.md"],
            "steps": [
                {
                    "title": "锁定镜像版本",
                    "actionType": "tool",
                    "instruction": "查询失败任务的镜像 tag、digest、启动命令和最近变更记录。",
                    "evidenceRequired": "image tag/digest、启动命令",
                    "toolName": "image_version",
                    "expectedResult": "明确当前运行镜像。",
                    "riskLevel": "low",
                },
                {
                    "title": "对比成功任务",
                    "actionType": "check",
                    "instruction": "找同项目最近一次成功任务，对比镜像 digest、CUDA、驱动和依赖版本。",
                    "evidenceRequired": "成功任务配置和失败任务配置",
                    "toolName": "task_status",
                    "expectedResult": "定位关键版本差异。",
                    "riskLevel": "low",
                },
                {
                    "title": "稳定镜像回归",
                    "actionType": "manual",
                    "instruction": "用上一个稳定镜像或固定 digest 做小样本回归验证。",
                    "evidenceRequired": "回归任务结果",
                    "toolName": "",
                    "expectedResult": "验证是否由镜像变更引发。",
                    "riskLevel": "medium",
                },
            ],
        },
    ]

    for item in samples:
        conn.execute(
            """
            INSERT OR IGNORE INTO t_runbook(
              runbook_id, title, service, scenario, severity, status, owner, version,
              trigger, summary, verification, escalation, risk_controls, tags,
              related_knowledge, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["runbookId"],
                item["title"],
                item["service"],
                item["scenario"],
                item["severity"],
                item["status"],
                item["owner"],
                item["version"],
                item["trigger"],
                item["summary"],
                item["verification"],
                item["escalation"],
                json.dumps(item["riskControls"], ensure_ascii=False),
                json.dumps(item["tags"], ensure_ascii=False),
                json.dumps(item["relatedKnowledge"], ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        for index, step in enumerate(item["steps"], start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO t_runbook_step(
                  step_id, runbook_id, step_order, title, action_type, instruction,
                  evidence_required, tool_name, expected_result, risk_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{item['runbookId']}-step-{index}",
                    item["runbookId"],
                    index,
                    step["title"],
                    step["actionType"],
                    step["instruction"],
                    step["evidenceRequired"],
                    step["toolName"],
                    step["expectedResult"],
                    step["riskLevel"],
                ),
            )


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


def list_feedback_reviews(status: Optional[str] = None, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    offset = (page - 1) * page_size
    params: List[Any] = []
    status_filter = ""
    if status:
        status_filter = "AND COALESCE(review.status, 'open') = ?"
        params.append(status)
    params.extend([page_size, offset])
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
              feedback.answer_message_id,
              feedback.user_id,
              feedback.conversation_id,
              feedback.query_message_id,
              feedback.reason,
              feedback.timestamp,
              query.content AS query_content,
              answer.content AS answer_content,
              review.quality_reason,
              review.status AS review_status,
              review.annotation,
              review.reviewer,
              review.eval_case_id,
              review.updated_at AS review_updated_at
            FROM t_chat_feedback AS feedback
            LEFT JOIN t_chat_memory AS query
              ON query.memory_id = feedback.query_message_id
             AND query.user_id = feedback.user_id
             AND query.conversation_id = feedback.conversation_id
            LEFT JOIN t_chat_memory AS answer
              ON answer.memory_id = feedback.answer_message_id
             AND answer.user_id = feedback.user_id
             AND answer.conversation_id = feedback.conversation_id
            LEFT JOIN t_feedback_review AS review
              ON review.answer_message_id = feedback.answer_message_id
             AND review.user_id = feedback.user_id
             AND review.conversation_id = feedback.conversation_id
            WHERE feedback.feedback = 'unlike'
              {status_filter}
            ORDER BY feedback.timestamp DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
    return [
        {
            "answerMessageId": row["answer_message_id"],
            "queryMessageId": row["query_message_id"],
            "userId": row["user_id"],
            "conversationId": row["conversation_id"],
            "query": row["query_content"] or "",
            "answer": row["answer_content"] or "",
            "feedbackReason": safe_json_loads(row["reason"], {}),
            "qualityReason": row["quality_reason"] or "未标注",
            "status": row["review_status"] or "open",
            "annotation": row["annotation"],
            "reviewer": row["reviewer"],
            "evalCaseId": row["eval_case_id"],
            "timestamp": row["timestamp"],
            "reviewUpdatedAt": row["review_updated_at"],
        }
        for row in rows
    ]


def annotate_feedback_review(
    answer_message_id: str,
    user_id: str,
    conversation_id: str,
    quality_reason: str,
    status: str = "open",
    annotation: Optional[str] = None,
    reviewer: Optional[str] = None,
    eval_case_id: Optional[str] = None,
) -> Dict[str, Any]:
    timestamp = now_text()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_feedback_review(
              answer_message_id, user_id, conversation_id, quality_reason, status,
              annotation, reviewer, eval_case_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(answer_message_id, user_id, conversation_id)
            DO UPDATE SET
              quality_reason = excluded.quality_reason,
              status = excluded.status,
              annotation = excluded.annotation,
              reviewer = excluded.reviewer,
              eval_case_id = COALESCE(excluded.eval_case_id, t_feedback_review.eval_case_id),
              updated_at = excluded.updated_at
            """,
            (
                answer_message_id,
                user_id,
                conversation_id,
                quality_reason,
                status,
                annotation,
                reviewer,
                eval_case_id,
                timestamp,
            ),
        )
    rows = list_feedback_reviews(page=1, page_size=200)
    return next(
        item
        for item in rows
        if item["answerMessageId"] == answer_message_id
        and item["userId"] == user_id
        and item["conversationId"] == conversation_id
    )


def upsert_eval_case(
    title: str,
    query: str,
    expected_answer: Optional[str] = None,
    required_steps: Optional[List[str]] = None,
    forbidden_content: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    case_id: Optional[str] = None,
    source_feedback_id: Optional[str] = None,
    status: str = "active",
) -> Dict[str, Any]:
    timestamp = now_text()
    effective_case_id = case_id or str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_eval_case(
              case_id, title, query, expected_answer, required_steps, forbidden_content,
              tags, source_feedback_id, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id)
            DO UPDATE SET
              title = excluded.title,
              query = excluded.query,
              expected_answer = excluded.expected_answer,
              required_steps = excluded.required_steps,
              forbidden_content = excluded.forbidden_content,
              tags = excluded.tags,
              source_feedback_id = excluded.source_feedback_id,
              status = excluded.status,
              updated_at = excluded.updated_at
            """,
            (
                effective_case_id,
                title,
                query,
                expected_answer,
                json.dumps(required_steps or [], ensure_ascii=False),
                json.dumps(forbidden_content or [], ensure_ascii=False),
                json.dumps(tags or [], ensure_ascii=False),
                source_feedback_id,
                status,
                timestamp,
                timestamp,
            ),
        )
    return get_eval_case(effective_case_id) or {}


def get_eval_case(case_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT case_id, title, query, expected_answer, required_steps, forbidden_content,
                   tags, source_feedback_id, status, created_at, updated_at
            FROM t_eval_case
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "caseId": row["case_id"],
        "title": row["title"],
        "query": row["query"],
        "expectedAnswer": row["expected_answer"],
        "requiredSteps": json.loads(row["required_steps"] or "[]"),
        "forbiddenContent": json.loads(row["forbidden_content"] or "[]"),
        "tags": json.loads(row["tags"] or "[]"),
        "sourceFeedbackId": row["source_feedback_id"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def list_eval_cases(status: Optional[str] = "active", page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
    offset = (page - 1) * page_size
    params: List[Any] = []
    where = ""
    if status:
        where = "WHERE status = ?"
        params.append(status)
    params.extend([page_size, offset])
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT case_id, title, query, expected_answer, required_steps, forbidden_content,
                   tags, source_feedback_id, status, created_at, updated_at
            FROM t_eval_case
            {where}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
    return [
        {
            "caseId": row["case_id"],
            "title": row["title"],
            "query": row["query"],
            "expectedAnswer": row["expected_answer"],
            "requiredSteps": json.loads(row["required_steps"] or "[]"),
            "forbiddenContent": json.loads(row["forbidden_content"] or "[]"),
            "tags": json.loads(row["tags"] or "[]"),
            "sourceFeedbackId": row["source_feedback_id"],
            "status": row["status"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


def save_eval_run(run: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    timestamp = now_text()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_eval_run(
              run_id, name, variant, prompt_version, retrieval_threshold, model,
              case_count, pass_count, avg_score, knowledge_hit_rate, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["runId"],
                run["name"],
                run["variant"],
                run.get("promptVersion"),
                run.get("retrievalThreshold"),
                run.get("model"),
                run["caseCount"],
                run["passCount"],
                run["avgScore"],
                run["knowledgeHitRate"],
                timestamp,
            ),
        )
        for result in results:
            conn.execute(
                """
                INSERT INTO t_eval_result(
                  result_id, run_id, case_id, answer, score, passed, checks,
                  knowledge_hit, error, total_ms, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    run["runId"],
                    result["caseId"],
                    result.get("answer"),
                    result["score"],
                    1 if result["passed"] else 0,
                    json.dumps(result["checks"], ensure_ascii=False),
                    1 if result.get("knowledgeHit") else 0,
                    result.get("error"),
                    int(result.get("totalMs") or 0),
                    timestamp,
                ),
            )
    return get_eval_run(run["runId"]) or {}


def get_eval_run(run_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        run = conn.execute(
            """
            SELECT run_id, name, variant, prompt_version, retrieval_threshold, model,
                   case_count, pass_count, avg_score, knowledge_hit_rate, created_at
            FROM t_eval_run
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if not run:
            return None
        results = conn.execute(
            """
            SELECT result_id, run_id, case_id, answer, score, passed, checks,
                   knowledge_hit, error, total_ms, created_at
            FROM t_eval_result
            WHERE run_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (run_id,),
        ).fetchall()
    return {
        "runId": run["run_id"],
        "name": run["name"],
        "variant": run["variant"],
        "promptVersion": run["prompt_version"],
        "retrievalThreshold": run["retrieval_threshold"],
        "model": run["model"],
        "caseCount": run["case_count"],
        "passCount": run["pass_count"],
        "passRate": round(run["pass_count"] / run["case_count"], 4) if run["case_count"] else 0,
        "avgScore": run["avg_score"],
        "knowledgeHitRate": run["knowledge_hit_rate"],
        "createdAt": run["created_at"],
        "results": [
            {
                "resultId": row["result_id"],
                "runId": row["run_id"],
                "caseId": row["case_id"],
                "answer": row["answer"],
                "score": row["score"],
                "passed": bool(row["passed"]),
                "checks": json.loads(row["checks"] or "{}"),
                "knowledgeHit": bool(row["knowledge_hit"]),
                "error": row["error"],
                "totalMs": row["total_ms"],
                "createdAt": row["created_at"],
            }
            for row in results
        ],
    }


def list_eval_runs(page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
    offset = (page - 1) * page_size
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, name, variant, prompt_version, retrieval_threshold, model,
                   case_count, pass_count, avg_score, knowledge_hit_rate, created_at
            FROM t_eval_run
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()
    return [
        {
            "runId": row["run_id"],
            "name": row["name"],
            "variant": row["variant"],
            "promptVersion": row["prompt_version"],
            "retrievalThreshold": row["retrieval_threshold"],
            "model": row["model"],
            "caseCount": row["case_count"],
            "passCount": row["pass_count"],
            "passRate": round(row["pass_count"] / row["case_count"], 4) if row["case_count"] else 0,
            "avgScore": row["avg_score"],
            "knowledgeHitRate": row["knowledge_hit_rate"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def upsert_ab_experiment(
    name: str,
    variants: List[str],
    traffic_split: Dict[str, float],
    primary_metric: str = "satisfactionRate",
    status: str = "draft",
    notes: Optional[str] = None,
    experiment_id: Optional[str] = None,
) -> Dict[str, Any]:
    timestamp = now_text()
    effective_id = experiment_id or str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO t_ab_experiment(
              experiment_id, name, status, variants, traffic_split, primary_metric, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(experiment_id)
            DO UPDATE SET
              name = excluded.name,
              status = excluded.status,
              variants = excluded.variants,
              traffic_split = excluded.traffic_split,
              primary_metric = excluded.primary_metric,
              notes = excluded.notes,
              updated_at = excluded.updated_at
            """,
            (
                effective_id,
                name,
                status,
                json.dumps(variants, ensure_ascii=False),
                json.dumps(traffic_split, ensure_ascii=False),
                primary_metric,
                notes,
                timestamp,
                timestamp,
            ),
        )
    return list_ab_experiments(experiment_id=effective_id)[0]


def list_ab_experiments(experiment_id: Optional[str] = None) -> List[Dict[str, Any]]:
    params: List[Any] = []
    where = ""
    if experiment_id:
        where = "WHERE experiment_id = ?"
        params.append(experiment_id)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT experiment_id, name, status, variants, traffic_split, primary_metric, notes, created_at, updated_at
            FROM t_ab_experiment
            {where}
            ORDER BY updated_at DESC, created_at DESC
            """,
            params,
        ).fetchall()
    return [
        {
            "experimentId": row["experiment_id"],
            "name": row["name"],
            "status": row["status"],
            "variants": json.loads(row["variants"] or "[]"),
            "trafficSplit": json.loads(row["traffic_split"] or "{}"),
            "primaryMetric": row["primary_metric"],
            "notes": row["notes"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


def _runbook_from_row(row: sqlite3.Row, steps: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "runbookId": row["runbook_id"],
        "title": row["title"],
        "service": row["service"],
        "scenario": row["scenario"],
        "severity": row["severity"],
        "status": row["status"],
        "owner": row["owner"],
        "version": row["version"],
        "trigger": row["trigger"],
        "summary": row["summary"],
        "verification": row["verification"],
        "escalation": row["escalation"],
        "riskControls": safe_json_loads(row["risk_controls"], []),
        "tags": safe_json_loads(row["tags"], []),
        "relatedKnowledge": safe_json_loads(row["related_knowledge"], []),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "steps": steps or [],
    }


def _runbook_step_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "stepId": row["step_id"],
        "runbookId": row["runbook_id"],
        "order": row["step_order"],
        "title": row["title"],
        "actionType": row["action_type"],
        "instruction": row["instruction"],
        "evidenceRequired": row["evidence_required"],
        "toolName": row["tool_name"],
        "expectedResult": row["expected_result"],
        "riskLevel": row["risk_level"],
    }


def list_runbooks(
    status: Optional[str] = None,
    service: Optional[str] = None,
    scenario: Optional[str] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    params: List[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if service:
        where.append("service = ?")
        params.append(service)
    if scenario:
        where.append("scenario = ?")
        params.append(scenario)
    if query:
        like = f"%{query}%"
        where.append("(title LIKE ? OR trigger LIKE ? OR summary LIKE ? OR tags LIKE ?)")
        params.extend([like, like, like, like])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT runbook_id, title, service, scenario, severity, status, owner, version,
                   trigger, summary, verification, escalation, risk_controls, tags,
                   related_knowledge, created_at, updated_at
            FROM t_runbook
            {where_sql}
            ORDER BY
              CASE status WHEN 'review' THEN 0 WHEN 'draft' THEN 1 WHEN 'published' THEN 2 ELSE 3 END,
              CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
              updated_at DESC
            """,
            params,
        ).fetchall()
        counts = {
            row["runbook_id"]: row["step_count"]
            for row in conn.execute(
                "SELECT runbook_id, COUNT(*) AS step_count FROM t_runbook_step GROUP BY runbook_id"
            ).fetchall()
        }
    result = []
    for row in rows:
        item = _runbook_from_row(row)
        item["stepCount"] = counts.get(row["runbook_id"], 0)
        result.append(item)
    return result


def get_runbook(runbook_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT runbook_id, title, service, scenario, severity, status, owner, version,
                   trigger, summary, verification, escalation, risk_controls, tags,
                   related_knowledge, created_at, updated_at
            FROM t_runbook
            WHERE runbook_id = ?
            """,
            (runbook_id,),
        ).fetchone()
        if not row:
            return None
        step_rows = conn.execute(
            """
            SELECT step_id, runbook_id, step_order, title, action_type, instruction,
                   evidence_required, tool_name, expected_result, risk_level
            FROM t_runbook_step
            WHERE runbook_id = ?
            ORDER BY step_order ASC, rowid ASC
            """,
            (runbook_id,),
        ).fetchall()
    return _runbook_from_row(row, [_runbook_step_from_row(step) for step in step_rows])


def upsert_runbook(
    title: str,
    service: str = "Wise",
    scenario: str = "模型任务",
    severity: str = "P2",
    status: str = "draft",
    owner: Optional[str] = None,
    version: str = "v1",
    trigger: Optional[str] = None,
    summary: Optional[str] = None,
    verification: Optional[str] = None,
    escalation: Optional[str] = None,
    risk_controls: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    related_knowledge: Optional[List[str]] = None,
    steps: Optional[List[Dict[str, Any]]] = None,
    runbook_id: Optional[str] = None,
) -> Dict[str, Any]:
    timestamp = now_text()
    effective_id = runbook_id or str(uuid.uuid4())
    with connect() as conn:
        existing = conn.execute("SELECT created_at FROM t_runbook WHERE runbook_id = ?", (effective_id,)).fetchone()
        created_at = existing["created_at"] if existing else timestamp
        conn.execute(
            """
            INSERT INTO t_runbook(
              runbook_id, title, service, scenario, severity, status, owner, version,
              trigger, summary, verification, escalation, risk_controls, tags,
              related_knowledge, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(runbook_id)
            DO UPDATE SET
              title = excluded.title,
              service = excluded.service,
              scenario = excluded.scenario,
              severity = excluded.severity,
              status = excluded.status,
              owner = excluded.owner,
              version = excluded.version,
              trigger = excluded.trigger,
              summary = excluded.summary,
              verification = excluded.verification,
              escalation = excluded.escalation,
              risk_controls = excluded.risk_controls,
              tags = excluded.tags,
              related_knowledge = excluded.related_knowledge,
              updated_at = excluded.updated_at
            """,
            (
                effective_id,
                title,
                service,
                scenario,
                severity,
                status,
                owner,
                version,
                trigger,
                summary,
                verification,
                escalation,
                json.dumps(risk_controls or [], ensure_ascii=False),
                json.dumps(tags or [], ensure_ascii=False),
                json.dumps(related_knowledge or [], ensure_ascii=False),
                created_at,
                timestamp,
            ),
        )
        conn.execute("DELETE FROM t_runbook_step WHERE runbook_id = ?", (effective_id,))
        for index, step in enumerate(steps or [], start=1):
            conn.execute(
                """
                INSERT INTO t_runbook_step(
                  step_id, runbook_id, step_order, title, action_type, instruction,
                  evidence_required, tool_name, expected_result, risk_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step.get("stepId") or str(uuid.uuid4()),
                    effective_id,
                    int(step.get("order") or index),
                    step.get("title") or f"步骤 {index}",
                    step.get("actionType") or "check",
                    step.get("instruction") or "",
                    step.get("evidenceRequired"),
                    step.get("toolName"),
                    step.get("expectedResult"),
                    step.get("riskLevel") or "low",
                ),
            )
    return get_runbook(effective_id) or {}


def update_runbook_status(runbook_id: str, status: str) -> Optional[Dict[str, Any]]:
    allowed_statuses = {"draft", "review", "published", "archived"}
    if status not in allowed_statuses:
        raise ValueError(f"Unsupported runbook status: {status}")
    with connect() as conn:
        row = conn.execute("SELECT runbook_id FROM t_runbook WHERE runbook_id = ?", (runbook_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE t_runbook SET status = ?, updated_at = ? WHERE runbook_id = ?",
            (status, now_text(), runbook_id),
        )
    return get_runbook(runbook_id)


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
              COUNT(DISTINCT CASE WHEN m.type IN ('user', 'query') THEN m.user_id END) AS active_users,
              COUNT(DISTINCT CASE WHEN m.type IN ('user', 'query') THEN m.user_id || ':' || m.conversation_id END) AS conversation_count,
              SUM(CASE WHEN m.type IN ('user', 'query') THEN 1 ELSE 0 END) AS question_count,
              SUM(CASE WHEN m.type IN ('assistant', 'answer') THEN 1 ELSE 0 END) AS assistant_reply_count
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
              COUNT(DISTINCT CASE WHEN m.type IN ('user', 'query') THEN m.user_id END) AS active_users,
              COUNT(DISTINCT CASE WHEN m.type IN ('user', 'query') THEN m.user_id || ':' || m.conversation_id END) AS conversation_count,
              SUM(CASE WHEN m.type IN ('user', 'query') THEN 1 ELSE 0 END) AS question_count,
              SUM(CASE WHEN m.type IN ('assistant', 'answer') THEN 1 ELSE 0 END) AS assistant_reply_count
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
            WHERE {chat_where} AND m.type IN ('user', 'query')
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
        reason = safe_json_loads(row["reason"], {})
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
