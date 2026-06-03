import json
import os
import sqlite3
from pathlib import Path

TEST_DB = Path(__file__).parent / "test_agent.db"
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
