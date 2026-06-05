import json
import os
import sqlite3
import time
from pathlib import Path

TEST_DB = Path(__file__).parent / "test_agent.db"
TEST_SKILL_DIR = Path(__file__).parents[1] / "skills" / "local_markdown_knowledge"
os.environ["WISE_AGENT_DB_PATH"] = str(TEST_DB)

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


client = TestClient(app)


def test_health_ready_and_login_endpoints():
    TEST_DB.unlink(missing_ok=True)
    init_db()

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["database"]["ok"] is True

    failed_login = client.post("/agent/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert failed_login.json()["result"]["code"] == 401

    login = client.post("/agent/v1/auth/login", json={"username": "admin", "password": "change-me"})
    payload = login.json()["result"]
    assert payload["code"] == 0
    assert payload["data"]["role"] == "admin"
    assert payload["data"]["token"]

    me = client.get("/agent/v1/auth/me")
    assert me.json()["result"]["data"]["role"] == "admin"


def test_chat_stream_feedback_and_history():
    TEST_DB.unlink(missing_ok=True)
    init_db()
    conversation_id = "conv-test-001"
    request = {
        "query": "1401027 insufficient memory 报错",
        "needDeepThinking": 1,
        "prompt": "mlops-agent",
        "context": {
            "userId": "l0123456",
            "conversationId": conversation_id,
            "service": "Wise",
            "scene": "模型任务",
            "title": "MTP训练任务诊断",
        },
    }

    with client.stream("POST", "/agent/v1/assistant/chat", json=request) as response:
        assert response.status_code == 200
        chunks = []
        message_id = None
        query_message_id = None
        trace_id = None
        diagnostic_state = None
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line.removeprefix("data: "))
            chunks.append(payload["content"])
            message_id = payload["messageId"]
            query_message_id = payload["queryMessageId"]
            trace_id = payload["traceId"]
            diagnostic_state = payload["diagnosticState"]

    answer_text = "".join(chunks)
    assert "可解释诊断链路" in answer_text
    assert "根因候选" in answer_text
    assert "风险提示" in answer_text
    assert message_id
    assert query_message_id
    assert trace_id
    assert diagnostic_state["currentStep"]

    trace_response = client.post("/agent/v1/assistant/trace/detail", json={"traceId": trace_id})
    trace = trace_response.json()["result"]["data"]
    assert trace["traceId"] == trace_id
    assert trace["diagnosticState"]["currentStep"] == diagnostic_state["currentStep"]
    span_kinds = {span["kind"] for span in trace["spans"]}
    assert {"agent", "retriever", "guardrail", "tool", "llm"}.issubset(span_kinds)

    state_response = client.post(
        "/agent/v1/assistant/diagnostic/state",
        json={"userId": "l0123456", "conversationId": conversation_id},
    )
    state = state_response.json()["result"]["data"]
    assert state["currentStep"] == diagnostic_state["currentStep"]

    feedback = {
        "feedback": "unlike",
        "reason": {
            "feedbackInfo": "回答不清楚",
            "feedbackInfoTypes": ["回答没有用", "没有理解我的意图"],
        },
        "context": {
            "userId": "l0123456",
            "conversationId": conversation_id,
            "messageId": message_id,
            "queryMessageId": query_message_id,
        },
    }
    feedback_response = client.post("/agent/v1/assistant/feedback", json=feedback)
    assert feedback_response.json()["result"]["code"] == 0

    conversation_response = client.post(
        "/agent/v1/assistant/conversation/list",
        json={"userId": "l0123456", "conversationId": conversation_id},
    )
    conversations = conversation_response.json()["result"]["data"]
    assert conversations[0]["conversationId"] == conversation_id

    chat_response = client.post(
        "/agent/v1/assistant/chat/list",
        json={"userId": "l0123456", "conversationId": conversation_id, "page": 1, "pageSize": 10},
    )
    chats = chat_response.json()["result"]["data"]
    assert [item["type"] for item in chats] == ["user", "assistant"]
    assert chats[1]["feedbackInfo"]["feedback"] == "unlike"
    assert chats[1]["queryMessageId"] == query_message_id
    assert chats[1]["traceId"] == trace_id


def test_feedback_without_query_message_id_is_recorded_in_database():
    TEST_DB.unlink(missing_ok=True)
    init_db()
    conversation_id = "conv-test-feedback-fallback"
    request = {
        "query": "任务内存不足怎么处理",
        "needDeepThinking": 0,
        "context": {
            "userId": "l0123456",
            "conversationId": conversation_id,
            "service": "Wise",
            "scene": "模型任务",
            "title": "MTP训练任务诊断",
        },
    }

    with client.stream("POST", "/agent/v1/assistant/chat", json=request) as response:
        message_id = None
        query_message_id = None
        for line in response.iter_lines():
            if line and line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
                message_id = payload["messageId"]
                query_message_id = payload["queryMessageId"]

    feedback_response = client.post(
        "/agent/v1/assistant/feedback",
        json={
            "feedback": "like",
            "context": {
                "userId": "l0123456",
                "conversationId": conversation_id,
                "messageId": message_id,
            },
        },
    )

    assert feedback_response.json()["result"]["code"] == 0

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT answer_message_id, query_message_id, feedback, reason
        FROM t_chat_feedback
        WHERE answer_message_id = ?
        """,
        (message_id,),
    ).fetchone()
    conn.close()

    assert row["answer_message_id"] == message_id
    assert row["query_message_id"] == query_message_id
    assert row["feedback"] == "like"


def test_ops_dashboard_counts_usage_and_feedback():
    TEST_DB.unlink(missing_ok=True)
    init_db()

    def run_chat(conversation_id, user_id, query):
        request = {
            "query": query,
            "needDeepThinking": 0,
            "context": {
                "userId": user_id,
                "conversationId": conversation_id,
                "service": "Wise",
                "scene": "模型任务",
                "title": "MTP训练任务诊断",
            },
        }
        with client.stream("POST", "/agent/v1/assistant/chat", json=request) as response:
            message_id = None
            query_message_id = None
            for line in response.iter_lines():
                if line and line.startswith("data: "):
                    payload = json.loads(line.removeprefix("data: "))
                    message_id = payload["messageId"]
                    query_message_id = payload["queryMessageId"]
        return message_id, query_message_id

    answer_1, query_1 = run_chat("conv-ops-001", "l0123456", "任务内存不足怎么处理")
    answer_2, query_2 = run_chat("conv-ops-002", "l0654321", "GPU OOM 如何排查")

    client.post(
        "/agent/v1/assistant/feedback",
        json={
            "feedback": "like",
            "context": {
                "userId": "l0123456",
                "conversationId": "conv-ops-001",
                "messageId": answer_1,
                "queryMessageId": query_1,
            },
        },
    )
    client.post(
        "/agent/v1/assistant/feedback",
        json={
            "feedback": "unlike",
            "reason": {
                "feedbackInfo": "缺少日志分析",
                "feedbackInfoTypes": ["缺少操作步骤"],
            },
            "context": {
                "userId": "l0654321",
                "conversationId": "conv-ops-002",
                "messageId": answer_2,
                "queryMessageId": query_2,
            },
        },
    )

    response = client.post("/agent/v1/ops/dashboard", json={"service": "Wise", "scene": "模型任务"})
    data = response.json()["result"]["data"]

    assert data["summary"]["activeUsers"] == 2
    assert data["summary"]["questionCount"] == 2
    assert data["summary"]["assistantReplyCount"] == 2
    assert data["summary"]["likeCount"] == 1
    assert data["summary"]["unlikeCount"] == 1
    assert data["summary"]["feedbackRate"] == 1
    assert data["reasonTop"][0]["reason"] == "缺少操作步骤"
    assert data["recentUnlikes"][0]["query"] == "GPU OOM 如何排查"
    assert {item["userId"] for item in data["topUsers"]} == {"l0123456", "l0654321"}


def test_knowledge_save_search_and_chat_grounding():
    TEST_DB.unlink(missing_ok=True)
    init_db()
    knowledge_file = TEST_SKILL_DIR / "knowledge" / "login-runbook.md"
    if knowledge_file.exists():
        knowledge_file.unlink()

    save_response = client.post(
        "/agent/v1/knowledge/save",
        json={
            "title": "登录失败排查",
            "filename": "login-runbook.md",
            "category": "登录认证",
            "tags": ["SSO", "登录"],
            "owner": "平台运维",
            "visibility": "internal",
            "content": "# 登录问题\n\n## 登录失败排查\n\n登录失败时先检查账号是否被禁用，再检查密码错误次数和 SSO 服务状态。",
        },
    )
    assert save_response.json()["result"]["code"] == 0
    assert knowledge_file.exists()

    list_response = client.post("/agent/v1/knowledge/list")
    files = list_response.json()["result"]["data"]
    saved = next(item for item in files if item["filename"] == "login-runbook.md")
    assert saved["knowledgeId"]
    assert saved["contentHash"]
    assert saved["updatedAt"]
    assert saved["status"] == "published"
    assert saved["category"] == "登录认证"
    assert saved["tags"] == ["SSO", "登录"]

    first_updated_at = saved["updatedAt"]
    time.sleep(1.1)
    second_list_response = client.post("/agent/v1/knowledge/list")
    second_files = second_list_response.json()["result"]["data"]
    second_saved = next(item for item in second_files if item["filename"] == "login-runbook.md")
    assert second_saved["updatedAt"] == first_updated_at

    revision_response = client.post(
        "/agent/v1/knowledge/revision/list",
        json={"filename": "login-runbook.md", "page": 1, "pageSize": 10},
    )
    revisions = revision_response.json()["result"]["data"]
    assert revisions
    assert revisions[0]["filename"] == "login-runbook.md"
    assert "登录失败" in revisions[0]["content"]

    detail_response = client.post(
        "/agent/v1/knowledge/detail",
        json={"filename": "login-runbook.md"},
    )
    detail = detail_response.json()["result"]["data"]
    assert detail["filename"] == "login-runbook.md"
    assert "SSO 服务状态" in detail["content"]
    assert detail["owner"] == "平台运维"

    archive_response = client.post(
        "/agent/v1/knowledge/status",
        json={"filename": "login-runbook.md", "status": "archived", "reviewNotes": "临时下线验证"},
    )
    assert archive_response.json()["result"]["data"]["status"] == "archived"

    archived_search_response = client.post(
        "/agent/v1/knowledge/search",
        json={"query": "SSO 服务状态", "topK": 3},
    )
    assert archived_search_response.json()["result"]["data"] == []

    publish_response = client.post(
        "/agent/v1/knowledge/status",
        json={"filename": "login-runbook.md", "status": "published", "reviewNotes": "审核通过"},
    )
    assert publish_response.json()["result"]["data"]["status"] == "published"

    update_response = client.post(
        "/agent/v1/knowledge/save",
        json={
            "title": "登录失败排查",
            "filename": "login-runbook.md",
            "category": "登录认证",
            "tags": ["SSO", "登录", "认证日志"],
            "content": "# 登录问题\n\n## 登录失败排查\n\n登录失败时先检查账号状态，并记录认证日志错误码。",
        },
    )
    assert update_response.json()["result"]["code"] == 0

    updated_detail_response = client.post(
        "/agent/v1/knowledge/detail",
        json={"filename": "login-runbook.md"},
    )
    updated_detail = updated_detail_response.json()["result"]["data"]
    assert updated_detail["title"] == "登录失败排查"
    assert updated_detail["content"].startswith("# 登录失败排查")
    assert "认证日志错误码" in updated_detail["content"]

    updated_revision_response = client.post(
        "/agent/v1/knowledge/revision/list",
        json={"filename": "login-runbook.md", "page": 1, "pageSize": 10},
    )
    updated_revisions = updated_revision_response.json()["result"]["data"]
    assert len(updated_revisions) >= 2
    assert "认证日志错误码" in updated_revisions[0]["content"]
    assert updated_revisions[0]["category"] == "登录认证"
    assert "认证日志" in updated_revisions[0]["tags"]

    search_response = client.post(
        "/agent/v1/knowledge/search",
        json={"query": "知识库里登录失败怎么处理", "topK": 3},
    )
    results = search_response.json()["result"]["data"]
    assert results
    assert "登录失败" in results[0]["content"]

    request = {
        "query": "根据知识库回答：登录失败怎么处理？",
        "needDeepThinking": 0,
        "context": {
            "userId": "l0123456",
            "conversationId": "conv-test-knowledge",
            "service": "Wise",
            "scene": "模型任务",
            "title": "MTP训练任务诊断",
        },
    }
    with client.stream("POST", "/agent/v1/assistant/chat", json=request) as response:
        answer = ""
        for line in response.iter_lines():
            if line and line.startswith("data: "):
                answer += json.loads(line.removeprefix("data: "))["content"]

    assert "根据本地知识库检索结果" in answer
    assert "login-runbook.md" in answer

    unlike_response = client.post(
        "/agent/v1/assistant/feedback",
        json={
            "feedback": "unlike",
            "reason": {
                "feedbackInfo": "需要补充更多步骤",
                "feedbackInfoTypes": ["缺少操作步骤"],
            },
            "context": {
                "userId": "l0123456",
                "conversationId": "conv-test-knowledge",
                "messageId": "missing-answer-id",
                "queryMessageId": "missing-query-id",
            },
        },
    )
    assert unlike_response.json()["result"]["code"] == 0

    gap_response = client.post("/agent/v1/knowledge/gap/list", json={"page": 1, "pageSize": 10})
    gaps = gap_response.json()["result"]["data"]
    assert gaps
    assert gaps[0]["reason"]["feedbackInfo"] == "需要补充更多步骤"
