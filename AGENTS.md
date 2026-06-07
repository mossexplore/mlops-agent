# AGENTS.md

本文件是 Wise MLOps Agent 项目的协作约束。每次开始任务前先阅读本文件，并在修改代码、运行测试、提交 GitHub 前对照执行。

## 回复规则

- 每次回复前先称呼用户为“乾坤天龙”。

## 项目定位

- 项目名称：Wise MLOps Agent。
- 技术栈：Python FastAPI 后端、SQLite 本地存储、原生 HTML/CSS/JavaScript 前端。
- 核心页面：
  - `/`：诊断会话工作台。
  - `/knowledge`：本地 Markdown 知识库管理。
  - `/ops`：运营看板。
  - `/quality`：质量评估与反馈闭环。
- 核心目标：把普通问答助手逐步升级为可解释、可追踪、可评估、可运营的 MLOps 诊断 Agent。

## 代码结构

- `app/main.py`：FastAPI 路由、页面入口、API 编排。
- `app/database.py`：SQLite 建表、迁移兼容、数据读写与聚合查询。
- `app/diagnostics.py`：可解释诊断链路、guardrails、trace/span 生成。
- `app/knowledge.py`：本地 Markdown 知识库读写、检索、版本和状态管理。
- `app/quality.py`：反馈工作台、评测集、自动评测和 A/B 实验。
- `app/schemas.py`：API 请求/响应模型。
- `frontend/`：静态页面和原生 JS，不使用前后端分离框架。
- `skills/local_markdown_knowledge/`：本地知识库 skill、知识文件和索引脚本。
- `tests/test_api.py`：后端 API 与核心流程测试。

## 必须保护的数据

不要提交运行时数据、密钥、个人知识内容或本地缓存。

已被 `.gitignore` 忽略的内容必须继续保持忽略：

- `.venv/`
- `.env`、`.env.*`，但保留 `.env.example`
- `data/`
- `tests/test_agent.db`
- `skills/local_markdown_knowledge/indexes/`
- `skills/local_markdown_knowledge/knowledge/*.md`
- `__pycache__/`、`.pytest_cache/`、`*.pyc`、`.DS_Store`

如果任务涉及清理或重建 SQLite 数据库，必须先提醒风险。除非用户明确要求，不能删除或覆盖 `data/agent.db`。需要清库时，优先先创建备份，例如：

```bash
mkdir -p data/backups
cp data/agent.db data/backups/agent-$(date +%Y%m%d-%H%M%S).db
```

## 本地运行

推荐使用项目虚拟环境：

```bash
cd /Users/jack/Documents/mlops-agent
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

如果用命令直接运行，优先使用：

```bash
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

## 测试与验证

提交前至少运行：

```bash
.venv/bin/pytest -q
```

修改前端 JS 时同时运行对应语法检查：

```bash
node --check frontend/app.js
node --check frontend/knowledge.js
node --check frontend/ops.js
node --check frontend/quality.js
```

只需检查本次修改影响到的 JS 文件；若不确定，全部检查。

修改页面布局或交互后，应启动本地服务并在浏览器验证对应页面。重点确认：

- 页面能加载，无控制台错误。
- 主要按钮、表单、筛选、状态切换可点击且能调用后端接口。
- Markdown 响应按 Markdown 规范渲染，而不是裸文本。
- 底部输入框、侧边栏、下拉框和滚动区域不会互相挤压或遮挡。

## 后端约束

- 新接口统一走 `api_response` 响应结构。
- 新请求模型写入 `app/schemas.py`。
- 数据库表和兼容迁移写入 `app/database.py` 的 `init_db()` 及相关读写函数。
- 对历史数据要保持向后兼容。例如聊天消息历史中可能存在 `user/assistant` 或旧口径 `query/answer`，统计逻辑应兼容。
- 反馈 `reason` 可能是 JSON，也可能是旧的纯文本，读取时使用安全解析，不能让一条脏数据导致整个看板 500。
- Agent 诊断回答不能编造真实 MLOps 平台数据。缺少证据时必须提示补充任务 ID、日志、事件、监控截图等信息。
- 删除、重启、扩容、归档、发布等高风险动作必须提示人工确认。

## 前端约束

- 当前项目不是前后端分离架构，页面在 `frontend/` 下由 FastAPI 静态托管。
- 保持原生 HTML/CSS/JS 方式，不引入大型前端框架，除非用户明确要求架构升级。
- UI 应服务于运维/诊断工作台场景：信息密度适中、层级清晰、控件可扫描，不做营销页式设计。
- 新增页面时要在相关导航中同步加入口，例如 `index.html`、`knowledge.html`、`ops.html`、`quality.html`。
- 按钮必须有实际事件或明确禁用态，不能出现“看起来能点但无反应”的控件。
- 页面上的状态、筛选条件、列表数据应与后端字段保持一致。

## 知识库约束

- 聊天和检索测试只应使用 `published` 状态知识，避免草稿或归档内容污染回答。
- 知识保存、状态切换、版本历史应同时维护文件内容和 SQLite 元数据。
- 本地知识正文和索引属于运行时数据，不提交到 Git。
- 知识库相关问题要同时考虑：
  - 当前知识文件列表。
  - `t_knowledge_file` 当前元数据。
  - `t_knowledge_file_revision` 历史版本。
  - `t_knowledge_hit` 检索命中记录。

## 运营与质量闭环约束

- 运营看板关注：活跃用户、提问数、会话数、点赞数、点踩数、反馈率、点踩率、点踩原因、Top 用户。
- 质量闭环关注：点踩队列、人工标注、评测用例、评测运行、A/B 实验、知识命中率、满意率、无答案率、重复提问率、平均耗时。
- 点踩原因标准枚举：
  - `knowledge_missing`
  - `retrieval_error`
  - `generic_answer`
  - `unactionable_steps`
  - `scene_misclassification`
- 任何 prompt、检索、知识库、质量评估相关改动，都应考虑是否需要补充或更新测试用例。

## Git 与提交

- 提交前检查：

```bash
git status --short
git diff --check
.venv/bin/pytest -q
```

- 不要提交 `data/`、`.env`、本地知识正文、索引或缓存。
- 如果工作区有用户未要求处理的改动，不要回滚，不要擅自覆盖；先识别是否与当前任务相关。
- 提交信息使用简洁英文祈使句，例如：
  - `Add quality feedback loop dashboard`
  - `Fix ops dashboard data compatibility`
  - `Improve knowledge lifecycle UI`
- 推送到 GitHub 前确认当前分支和远程：

```bash
git branch --show-current
git remote -v
```

## 常用命令

```bash
# 启动服务
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 运行测试
.venv/bin/pytest -q

# 检查前端 JS
node --check frontend/app.js
node --check frontend/knowledge.js
node --check frontend/ops.js
node --check frontend/quality.js

# 查看数据库表
sqlite3 data/agent.db ".tables"

# 查看最近会话
sqlite3 data/agent.db "SELECT user_id,conversation_id,title,timestamp FROM t_conversation ORDER BY timestamp DESC LIMIT 10;"

# 查看反馈和质量标注
sqlite3 data/agent.db "SELECT f.feedback,r.quality_reason,r.status,COUNT(*) FROM t_chat_feedback f LEFT JOIN t_feedback_review r ON r.answer_message_id=f.answer_message_id AND r.user_id=f.user_id AND r.conversation_id=f.conversation_id GROUP BY f.feedback,r.quality_reason,r.status;"
```

## 完成任务时的交付说明

最终回复应简洁说明：

- 改了哪些模块。
- 解决了什么问题。
- 运行了哪些验证。
- 是否有未完成事项或需要用户重启本地服务。

如果涉及 GitHub，说明提交 hash、分支、推送结果。
