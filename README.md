# Wise MLOps Agent

一个按 `wisemlops-agent开发.md` 实现的 MLOps 诊断 Agent 示例项目，包含 FastAPI 后端、SSE 流式聊天、点赞/点踩反馈、历史会话查询和一个可直接访问的 Web 工作台。

## 功能

- `GET /healthz`：应用存活检查。
- `GET /readyz`：应用就绪检查，会验证数据库连接。
- `POST /agent/v1/auth/login`：管理员登录，生产环境可通过环境变量开启认证。
- `POST /agent/v1/auth/logout`：退出登录并清理会话 Cookie。
- `POST /agent/v1/assistant/chat`：用户提问，Agent 通过 `text/event-stream` 按 `data: {...}` 流式返回。
- `POST /agent/v1/assistant/feedback`：对 Agent 回复点赞、点踩或置为 `NONE`，点踩可提交原因。
- `POST /agent/v1/assistant/conversation/list`：查询用户历史会话列表。
- `POST /agent/v1/assistant/chat/list`：查询某个会话下的全部对话记录。
- `POST /agent/v1/knowledge/save`：保存本地 Markdown 知识，并自动重建检索索引。
- `POST /agent/v1/knowledge/list`：查询本地知识文件列表。
- `POST /agent/v1/knowledge/search`：检索本地 Markdown 知识片段。
- `POST /agent/v1/ops/dashboard`：查询运营看板聚合数据，包括日活、提问、会话、点赞、点踩和点踩原因。
- `GET /`：Web 聊天工作台，支持流式显示、历史会话和反馈。
- `GET /knowledge`：本地 Markdown 知识库管理页面。
- `GET /ops`：运营看板页面，支持按日期、用户、来源和场景筛选。

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
- 知识库管理：http://127.0.0.1:8000/knowledge
- 运营看板：http://127.0.0.1:8000/ops
- API 文档：http://127.0.0.1:8000/docs

首次启动会自动创建 `data/agent.db`。

## 生产化配置

本地开发默认不强制登录。生产部署建议复制 `.env.example` 为 `.env`，并至少修改：

```bash
WISE_ENV=production
WISE_AUTH_ENABLED=true
WISE_AUTH_SECRET=replace-with-a-long-random-secret
WISE_ADMIN_USERNAME=admin
WISE_ADMIN_PASSWORD=replace-with-a-strong-password
WISE_CORS_ORIGINS=http://your-domain.example.com
```

关键配置：

- `WISE_AGENT_DB_PATH`：SQLite 数据库路径，默认 `data/agent.db`。
- `WISE_AUTH_ENABLED`：是否开启页面和管理接口认证。
- `WISE_AUTH_SECRET`：会话签名密钥，生产环境必须改成强随机值。
- `WISE_ADMIN_USERNAME` / `WISE_ADMIN_PASSWORD`：管理员账号密码。
- `WISE_SESSION_TTL_SECONDS`：登录会话有效期。
- `WISE_CORS_ORIGINS`：允许跨域来源，多个地址用英文逗号分隔。

开启认证后，访问 `/`、`/knowledge`、`/ops` 会先进入 `/login`。知识库和运营看板接口需要管理员会话。

## Docker 部署

```bash
cp .env.example .env
# 编辑 .env 中的密钥、管理员密码和 CORS 域名
docker compose up --build
```

容器会把以下目录挂载到本地，避免运行数据进入镜像：

```text
data/
skills/local_markdown_knowledge/knowledge/
skills/local_markdown_knowledge/indexes/
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

## 本地 Markdown 知识库

本项目包含 `local_markdown_knowledge` skill：

```text
skills/local_markdown_knowledge/
  SKILL.md
  knowledge/
  scripts/
  indexes/
```

在 `/knowledge` 页面保存知识后，内容会写入：

```text
skills/local_markdown_knowledge/knowledge/
```

并自动重建检索索引：

```text
skills/local_markdown_knowledge/indexes/
```

为了避免上传本地知识内容和索引，`.gitignore` 已忽略：

```text
skills/local_markdown_knowledge/knowledge/*.md
skills/local_markdown_knowledge/indexes/
```

当用户问题显式包含“知识库 / 文档 / 手册 / 内部”等关键词，或检索分数足够高时，聊天接口会优先基于本地 Markdown 检索结果回答，并附来源文件与标题。

知识库历史数据会记录到 SQLite：

- `t_knowledge_file`：当前 Markdown 文件元信息，包括文件名、标题、路径、大小、内容 hash、预览、创建时间、更新时间。
- `t_knowledge_file_revision`：通过页面保存/更新知识时生成的历史版本，包括 revision id、知识文件 id、标题、完整内容、大小、内容 hash、保存时间。

可用下面命令查询：

```bash
sqlite3 data/agent.db "SELECT filename,title,size,updated_at FROM t_knowledge_file ORDER BY updated_at DESC;"
sqlite3 data/agent.db "SELECT filename,title,size,timestamp FROM t_knowledge_file_revision ORDER BY timestamp DESC;"
```

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

## 版权与许可

Copyright (c) 2026 Wise MLOps Agent contributors.

本项目使用 MIT License 开源许可，详情见 [LICENSE](./LICENSE)。
