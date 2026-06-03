# Wise MLOps Agent

一个按 `wisemlops-agent开发.md` 实现的 MLOps 诊断 Agent 示例项目，包含 FastAPI 后端、SSE 流式聊天、点赞/点踩反馈、历史会话查询和一个可直接访问的 Web 工作台。

## 功能

- `POST /agent/v1/assistant/chat`：用户提问，Agent 通过 `text/event-stream` 按 `data: {...}` 流式返回。
- `POST /agent/v1/assistant/feedback`：对 Agent 回复点赞、点踩或置为 `NONE`，点踩可提交原因。
- `POST /agent/v1/assistant/conversation/list`：查询用户历史会话列表。
- `POST /agent/v1/assistant/chat/list`：查询某个会话下的全部对话记录。
- `GET /`：Web 聊天工作台，支持流式显示、历史会话和反馈。

## 技术栈

- 后端：Python、FastAPI、Uvicorn
- 存储：SQLite，表结构对应设计文档中的 `t_conversation`、`t_chat_memory`、`t_conversation_context`、`t_chat_feedback`
- 前端：原生 Web Components 风格的 HTML/CSS/JavaScript，由 FastAPI 静态托管

## 启动方式

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 已经完成上述操作，后续每次操作：
cd /Users/jack/Documents/mlops-agent
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- Web 页面：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs

首次启动会自动创建 `data/agent.db`。

## 接口调试示例

### 流式聊天

```bash
curl -N -X POST http://127.0.0.1:8000/agent/v1/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "1401027 insufficient memory 报错",
    "needDeepThinking": 0,
    "prompt": "mlops-agent",
    "context": {
      "userId": "l0123456",
      "conversationId": "18b20e64-17fb-4585-9a69-ae1c8f101666",
      "service": "Wise",
      "scene": "模型任务",
      "title": "MTP训练任务诊断"
    }
  }'
```

### 反馈

```bash
curl -X POST http://127.0.0.1:8000/agent/v1/assistant/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "unlike",
    "reason": {
      "feedbackInfo": "回答不清楚",
      "feedbackInfoTypes": ["回答没有用", "没有理解我的意图"]
    },
    "context": {
      "userId": "l0123456",
      "conversationId": "18b20e64-17fb-4585-9a69-ae1c8f101666",
      "messageId": "替换为chat接口返回的messageId"
    }
  }'
```

## 测试

```bash
pytest
```
