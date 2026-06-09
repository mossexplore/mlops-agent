# Wise MLOps Agent

一个按 `wisemlops-agent开发.md` 实现的 MLOps 诊断 Agent 示例项目，包含 FastAPI 后端、SSE 流式聊天、点赞/点踩反馈、历史会话查询和一个可直接访问的 Web 工作台。前端为按 Claude Design 设计稿实现的单页控制台（React SPA），覆盖诊断会话、知识库、Runbook、运营看板、质量闭环五大工作台。

## 功能

- `GET /healthz`：应用存活检查。
- `GET /readyz`：应用就绪检查，会验证数据库连接。
- `POST /agent/v1/auth/login`：管理员登录，生产环境可通过环境变量开启认证。
- `POST /agent/v1/auth/logout`：退出登录并清理会话 Cookie。
- `POST /agent/v1/assistant/chat`：用户提问，Agent 通过 `text/event-stream` 按 `data: {...}` 流式返回。
- `POST /agent/v1/assistant/feedback`：对 Agent 回复点赞、点踩或置为 `NONE`，点踩可提交原因。
- `POST /agent/v1/assistant/conversation/list`：查询用户历史会话列表。
- `POST /agent/v1/assistant/chat/list`：查询某个会话下的全部对话记录。
- `POST /agent/v1/assistant/trace/detail`：查询一次 Agent 回复的 trace 和 span 明细。
- `POST /agent/v1/assistant/diagnostic/state`：查询某个会话的多轮诊断状态。
- `POST /agent/v1/quality/dashboard`：查询质量闭环工作台聚合数据。
- `POST /agent/v1/quality/feedback/list`：查询点踩反馈与人工标注队列。
- `POST /agent/v1/quality/feedback/annotate`：标注点踩原因，支持知识缺失、检索错误、回答泛泛、步骤不可执行、误判场景。
- `POST /agent/v1/quality/eval-case/save`：新增或更新固定评测用例。
- `POST /agent/v1/quality/eval-case/from-feedback`：将典型点踩反馈沉淀为评测用例。
- `POST /agent/v1/quality/eval/run`：运行固定评测集，产出通过率、平均分和知识命中率。
- `POST /agent/v1/quality/experiment/save`：保存 A/B 实验配置。
- `POST /agent/v1/knowledge/save`：保存本地 Markdown 知识，并自动重建检索索引。
- `POST /agent/v1/knowledge/list`：查询本地知识文件列表。
- `POST /agent/v1/knowledge/search`：检索本地 Markdown 知识片段。
- `POST /agent/v1/knowledge/status`：切换知识生命周期状态，支持草稿、待审核、已发布、已归档。
- `POST /agent/v1/knowledge/revision/list`：查询知识内容和状态变更版本历史。
- `POST /agent/v1/knowledge/gap/list`：查询由点踩反馈暴露出的知识缺口。
- `POST /agent/v1/runbook/list`：查询诊断 Runbook 列表，支持按状态、服务、场景和关键词筛选。
- `POST /agent/v1/runbook/detail`：查询 Runbook 元数据、诊断步骤、工具意图、证据要求和风险级别。
- `POST /agent/v1/runbook/save`：新增或更新 Runbook，不替代现有 Markdown 知识库。
- `POST /agent/v1/runbook/status`：切换 Runbook 生命周期状态，支持草稿、待审核、已发布、已归档。
- `POST /agent/v1/ops/dashboard`：查询运营看板聚合数据，包括日活、提问、会话、点赞、点踩和点踩原因。
- `GET /`：Web 聊天工作台，支持流式显示、历史会话和反馈。
- `GET /knowledge`：本地 Markdown 知识库管理页面。
- `GET /runbooks`：诊断 Runbook 编排页面，管理触发条件、证据、步骤、工具意图、验证方式和高风险护栏。
- `GET /ops`：运营看板页面，支持按日期、用户、来源和场景筛选。
- `GET /quality`：质量评估与反馈闭环工作台。

## 技术栈

- 后端：Python、FastAPI、Uvicorn
- 存储：SQLite，表结构对应设计文档中的 `t_conversation`、`t_chat_memory`、`t_conversation_context`、`t_chat_feedback`
- 前端：React 18 单页应用（SPA），由浏览器内 Babel 编译 JSX，无需打包构建，统一设计系统（深色主题、强调色、信息密度），由 FastAPI 静态托管

### 前端结构

前端位于 `frontend/`，由 FastAPI 在 `/static` 下托管，`index.html` 为单页入口，按路径（`/`、`/knowledge`、`/runbooks`、`/ops`、`/quality`）做客户端路由：

```text
frontend/
  index.html            # SPA 入口（React/Babel CDN）
  login.html / login.js # 登录页
  api.js                # 后端接口与 SSE 流式封装
  helpers.js            # Markdown 渲染、标签与工具函数
  app.jsx               # 侧栏 / 顶栏 / 路由外壳
  view-chat.jsx         # 诊断会话（SSE 流式 + Agent Trace + 多轮状态）
  view-knowledge.jsx    # 本地知识库管理
  view-runbooks.jsx     # 诊断 Runbook 编排
  view-ops.jsx          # 运营看板
  view-quality.jsx      # 质量评估与反馈闭环
  ui.jsx / icons.jsx    # 通用组件、图表与图标
  console.css / views.css / views2.css / extra.css  # 设计系统与视图样式
```

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
- Runbook 编排：http://127.0.0.1:8000/runbooks
- 运营看板：http://127.0.0.1:8000/ops
- 质量闭环：http://127.0.0.1:8000/quality
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

知识库支持治理元数据：

- 分类：例如登录认证、资源问题、训练任务。
- 标签：用于快速筛选、命中解释和后续评测集沉淀。
- 状态：`draft` 草稿、`review` 待审核、`published` 已发布、`archived` 已归档。
- 负责人、可见性、审核备注。

当用户问题显式包含“知识库 / 文档 / 手册 / 内部”等关键词，或检索分数足够高时，聊天接口会优先基于本地 Markdown 检索结果回答，并附来源文件与标题。为了避免草稿或过期知识污染回答，聊天和检索测试只使用 `published` 状态的知识。

### 检索：混合 RAG（稀疏 + 稠密）

知识检索采用业界常见的 **混合检索（Hybrid Retrieval）**，并对结果做相关性过滤：

- **稀疏分支**：纯 Python TF-IDF 余弦相似度，擅长报错码、英文关键词、精确词面匹配（如 `1401027`）。
- **稠密分支（可选）**：`sentence-transformers` 句向量 + `faiss` 向量检索，擅长中文自然语言、同义/口语化、改写提问（词面不重合也能命中）。
- **融合**：用 Reciprocal Rank Fusion（RRF）合并两路排名；返回的 `score` 回标定为真实相似度（保持与下游 0.18 阈值、`min_score` 过滤兼容）。
- **优雅降级**：未安装稠密依赖、模型无法加载（离线/无缓存）或显式关闭时，自动回退为纯 TF-IDF，功能不受影响。
- 切分、索引与 `published` 过滤逻辑保持不变；保存/切换状态时会自动重建稀疏与稠密两份索引。

默认是纯 TF-IDF。启用稠密/混合检索：

```bash
# 安装可选依赖（包含 torch，体积较大）
pip install -r skills/local_markdown_knowledge/requirements.txt
# 重建索引（首次会下载 embedding 模型，约 95MB）
python skills/local_markdown_knowledge/scripts/build_index.py
```

相关环境变量：

- `WISE_EMBED_ENABLED`：是否启用稠密检索，默认 `1`，设为 `0` 强制纯 TF-IDF。
- `WISE_EMBED_MODEL`：embedding 模型，默认 `BAAI/bge-small-zh-v1.5`（中文为主；如需更强跨语言可换 `BAAI/bge-m3` 等）。
- `WISE_EMBED_FLOOR`：稠密余弦的“相似度地板”，默认 `0.35`，用于把中文模型偏高的相似度基线重标定到 `[0,1]`，过滤弱相关噪声。

> 索引文件（`indexes/dense.faiss`、`indexes/dense_meta.json` 等）已在 `.gitignore` 中忽略，不会进入仓库。

知识库历史数据会记录到 SQLite：

- `t_knowledge_file`：当前 Markdown 文件元信息，包括文件名、标题、路径、大小、内容 hash、预览、创建时间、更新时间。
- `t_knowledge_file_revision`：通过页面保存/更新/切换状态时生成的历史版本，包括 revision id、知识文件 id、标题、完整内容、大小、内容 hash、状态、分类、标签、审核备注和保存时间。
- `t_knowledge_hit`：记录聊天或检索测试中的知识命中，用于后续分析知识命中率和点踩后的知识缺口。

可用下面命令查询：

```bash
sqlite3 data/agent.db "SELECT filename,title,size,updated_at FROM t_knowledge_file ORDER BY updated_at DESC;"
sqlite3 data/agent.db "SELECT filename,title,size,timestamp FROM t_knowledge_file_revision ORDER BY timestamp DESC;"
sqlite3 data/agent.db "SELECT channel,query,filename,score,timestamp FROM t_knowledge_hit ORDER BY timestamp DESC LIMIT 20;"
```

## 诊断 Runbook 流程

Runbook 是独立于 Markdown 知识库的诊断流程资产，不会替代 `/knowledge` 的本地知识管理。知识库更适合沉淀说明文档、FAQ 和背景资料；Runbook 更适合沉淀线上故障排查步骤、证据要求、工具意图、验证方式和高风险护栏。

首次初始化数据库时会幂等写入三条样例 Runbook：

- `1401027 insufficient memory 训练任务诊断`
- `训练任务 Pending / 调度失败诊断`
- `镜像 / CUDA / 依赖启动失败诊断`

Runbook 支持的治理字段：

- 服务、场景、严重级别、负责人、版本。
- 触发条件、流程摘要、验证方式、升级路径。
- 标签、关联知识、风险护栏。
- 状态：`draft` 草稿、`review` 待审核、`published` 已发布、`archived` 已归档。
- 诊断步骤：步骤标题、步骤类型、操作说明、所需证据、工具意图、预期结果、风险级别。

在 `/runbooks` 页面可以管理 Runbook 流程。页面左侧用于筛选和选择 Runbook，主编辑区维护元数据和诊断步骤，右侧执行视图会按当前步骤即时预览，并对 `high` 风险步骤展示高风险确认提示。

诊断会话页 `/` 中有 `Runbook 回答` 开关：

- 关闭时保持原有知识库 / 通用诊断链路。
- 开启时聊天请求会发送 `groundingMode: "runbook"`，只使用已发布 Runbook 组织回答，不再查询本地 Markdown 知识库。
- 当用户问题精确匹配已发布 Runbook 标题时，后端也会自动切换到 Runbook 模式，避免把 Runbook 标题误当普通知识库问题。
- Runbook 模式仍然通过 SSE 流式返回，回答会按 `步骤一`、`步骤二`、`步骤三` 这样的格式展开，并包含每步的操作、证据、预期结果、风险级别和工具意图。
- trace 会记录 `runbook_retrieval` span；知识库模式则记录 `knowledge_retrieval` span。

Runbook 相关表：

- `t_runbook`：Runbook 元数据，包括标题、服务、场景、严重级别、状态、触发条件、验证方式、升级路径、风险护栏和标签。
- `t_runbook_step`：Runbook 步骤，包括顺序、类型、操作说明、证据要求、工具意图、预期结果和风险级别。

可用下面命令查询：

```bash
sqlite3 data/agent.db "SELECT runbook_id,title,service,scenario,severity,status,updated_at FROM t_runbook ORDER BY updated_at DESC;"
sqlite3 data/agent.db "SELECT runbook_id,step_order,title,action_type,tool_name,risk_level FROM t_runbook_step ORDER BY runbook_id,step_order;"
```

## 可解释诊断 Agent

聊天接口不再只返回一段问答文本，而是把每次诊断拆成稳定链路：

- 问题识别：提取错误码、资源、日志、调度、镜像等信号。
- 场景判断：结合用户选择的来源、场景和上一轮诊断状态判断问题类型。
- 知识检索：只使用已发布知识片段，避免草稿污染回答。
- 工具调用计划：预留任务状态、日志、资源指标、镜像版本、调度事件等工具位；未接入真实平台前只记录意图，不编造平台数据。
- 根因候选：按证据给出多个候选原因和置信度。
- 建议动作：先验证、再处理，高风险动作需要人工确认。
- 风险提示：缺少证据时明确提示不确定性。
- 多轮状态：记录当前排查步骤、已确认事实、下一步需要补充的信息。

实现上借鉴 OpenAI Agents SDK 的 trace/span/guardrail 思路、Phoenix 的 OpenTelemetry 风格可观测链路，以及 LangSmith 的 run/span metadata 结构。本项目先落地为本地 SQLite，后续可再导出到 Phoenix、LangSmith 或 OpenTelemetry collector。

诊断相关表：

- `t_agent_trace`：一次 Agent 回复的端到端 trace，包含输入、输出、guardrails、诊断状态、耗时和错误。
- `t_agent_span`：trace 内每个步骤的 span，例如 `problem_identification`、`knowledge_retrieval`、`guardrails`、`tool_planning`、`response_generation`。
- `t_diagnostic_state`：会话级多轮诊断状态。

可用下面命令查询：

```bash
sqlite3 data/agent.db "SELECT trace_id,query,status,total_ms,created_at FROM t_agent_trace ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/agent.db "SELECT name,kind,status,duration_ms FROM t_agent_span WHERE trace_id='替换为traceId' ORDER BY started_at;"
sqlite3 data/agent.db "SELECT user_id,conversation_id,current_step,risk_level,updated_at FROM t_diagnostic_state ORDER BY updated_at DESC LIMIT 10;"
```

## 质量评估与反馈闭环

质量系统参考业界常见做法：

- LangSmith：把线上反馈沉淀到 annotation queue，并把典型问题加入 dataset 做回归实验。
- OpenAI Evals：用固定测试集、grader 和 run 对 prompt、模型、检索策略改动做可重复评测。
- RAG 评估实践：关注知识命中率、答案相关性、可执行性、风险边界和禁止内容。

本项目先落地一套本地 SQLite 质量闭环：

- 反馈工作台：管理员查看点踩记录，标注为 `knowledge_missing`、`retrieval_error`、`generic_answer`、`unactionable_steps`、`scene_misclassification`。
- 测试集沉淀：把典型问题保存为评测用例，包括输入问题、期望答案、必须包含步骤、禁止出现内容和标签。
- 自动评测：运行固定测试集，使用规则 grader 计算必须步骤命中、可执行动作、风险提示、知识命中和禁止内容违规。后续可替换为 LLM-as-judge。
- 回答质量指标：知识命中率、回答满意率、点踩率、无答案率、重复提问率、平均响应耗时。
- A/B 实验：记录不同 prompt、检索阈值、模型或策略的 variants、流量比例和主指标，用于后续在线对比。

相关表：

- `t_feedback_review`：点踩反馈人工标注与处理状态。
- `t_eval_case`：固定评测集。
- `t_eval_run` / `t_eval_result`：自动评测运行和单条结果。
- `t_ab_experiment`：A/B 实验配置。

可用下面命令查询：

```bash
sqlite3 data/agent.db "SELECT quality_reason,status,COUNT(*) FROM t_feedback_review GROUP BY quality_reason,status;"
sqlite3 data/agent.db "SELECT title,query,status,updated_at FROM t_eval_case ORDER BY updated_at DESC;"
sqlite3 data/agent.db "SELECT name,variant,case_count,pass_count,avg_score,knowledge_hit_rate,created_at FROM t_eval_run ORDER BY created_at DESC;"
```

## 接口调试示例

### 流式聊天

知识库 / 通用诊断模式：

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

Runbook 模式：

```bash
curl -N -X POST http://127.0.0.1:8000/agent/v1/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "1401027 insufficient memory 报错",
    "needDeepThinking": 0,
    "groundingMode": "runbook",
    "context": {
      "userId": "l0123456",
      "conversationId": "18b20e64-17fb-4585-9a69-ae1c8f101666",
      "service": "Wise",
      "scene": "模型任务",
      "title": "Runbook 模式诊断"
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

### Trace 明细

```bash
curl -X POST http://127.0.0.1:8000/agent/v1/assistant/trace/detail \
  -H "Content-Type: application/json" \
  -d '{"traceId":"替换为chat接口返回的traceId"}'
```

## 测试

```bash
pytest
```

## 版权与许可

Copyright (c) 2026 Wise MLOps Agent contributors.

本项目使用 MIT License 开源许可，详情见 [LICENSE](./LICENSE)。
