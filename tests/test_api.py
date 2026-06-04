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
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line.removeprefix("data: "))
            chunks.append(payload["content"])
            message_id = payload["messageId"]
            query_message_id = payload["queryMessageId"]

    assert "内存不足" in "".join(chunks)
    assert message_id
    assert query_message_id

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

    update_response = client.post(
        "/agent/v1/knowledge/save",
        json={
            "title": "登录失败排查",
            "filename": "login-runbook.md",
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
