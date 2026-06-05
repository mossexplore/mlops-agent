import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent import build_answer, stream_chunks
from .auth import (
    authenticate,
    clear_session_cookie,
    create_session_token,
    current_user,
    require_admin,
    require_page_session,
    set_session_cookie,
)
from .config import settings
from .database import (
    add_chat,
    check_db,
    get_ops_dashboard,
    init_db,
    list_chats,
    list_conversations,
    record_knowledge_hits,
    save_feedback,
    upsert_conversation,
)
from .knowledge import (
    build_grounded_answer,
    change_markdown_knowledge_status,
    get_markdown_knowledge_detail,
    list_markdown_knowledge_gaps,
    list_markdown_knowledge,
    list_markdown_knowledge_revisions,
    retrieve_knowledge,
    should_use_local_knowledge,
    write_markdown_knowledge,
)
from .schemas import (
    ChatListRequest,
    ChatRequest,
    ConversationListRequest,
    FeedbackRequest,
    KnowledgeDetailRequest,
    KnowledgeGapListRequest,
    KnowledgeRevisionListRequest,
    KnowledgeSaveRequest,
    KnowledgeSearchRequest,
    KnowledgeStatusRequest,
    LoginRequest,
    OpsDashboardRequest,
    api_response,
)


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def dump_model(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@app.get("/")
def index(request: Request) -> FileResponse:
    redirect = require_page_session(request)
    if redirect:
        return redirect
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/knowledge")
def knowledge_page(request: Request) -> FileResponse:
    redirect = require_page_session(request)
    if redirect:
        return redirect
    return FileResponse(STATIC_DIR / "knowledge.html")


@app.get("/ops")
def ops_page(request: Request) -> FileResponse:
    redirect = require_page_session(request)
    if redirect:
        return redirect
    return FileResponse(STATIC_DIR / "ops.html")


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/readyz")
def readyz():
    db = check_db()
    return {"status": "ok", "database": db, "authEnabled": settings.auth_enabled}


@app.post("/agent/v1/auth/login")
def login(request: LoginRequest, response: Response):
    user = authenticate(request.username, request.password)
    if not user:
        return api_response(data=None, code=401, des="用户名或密码错误")
    token = create_session_token(user["userId"], user["role"])
    set_session_cookie(response, token)
    return api_response(data={"userId": user["userId"], "role": user["role"], "token": token})


@app.post("/agent/v1/auth/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return api_response(data=None)


@app.get("/agent/v1/auth/me")
def me(user=Depends(require_admin)):
    return api_response(data={**user, "authEnabled": settings.auth_enabled})


@app.post("/agent/v1/assistant/chat")
async def chat(request: ChatRequest, _user=Depends(current_user)) -> StreamingResponse:
    context = request.context
    query_message_id = str(uuid.uuid4())
    answer_message_id = str(uuid.uuid4())
    query_send_time = int(time.time() * 1000)
    knowledge_results = retrieve_knowledge(request.query, top_k=5)
    record_knowledge_hits(
        channel="chat",
        query=request.query,
        results=knowledge_results,
        user_id=context.userId,
        conversation_id=context.conversationId,
        message_id=query_message_id,
    )
    if should_use_local_knowledge(request.query, knowledge_results):
        answer = build_grounded_answer(request.query, knowledge_results)
    else:
        answer = build_answer(request.query, request.needDeepThinking)

    upsert_conversation(
        user_id=context.userId,
        conversation_id=context.conversationId,
        title=context.title,
        service=context.service,
        scene=context.scene,
    )
    add_chat(query_message_id, context.userId, context.conversationId, "user", request.query)

    async def event_stream() -> AsyncIterator[str]:
        full_content = ""
        for chunk in stream_chunks(answer):
            full_content += chunk
            payload = {
                "content": chunk,
                "userId": context.userId,
                "conversationId": context.conversationId,
                "messageId": answer_message_id,
                "queryMessageId": query_message_id,
                "messageSendTime": int(time.time() * 1000),
                "querySendTime": query_send_time,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.035)
        add_chat(answer_message_id, context.userId, context.conversationId, "assistant", full_content)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/agent/v1/assistant/feedback")
def feedback(request: FeedbackRequest, _user=Depends(current_user)):
    save_feedback(
        answer_message_id=request.context.messageId,
        user_id=request.context.userId,
        conversation_id=request.context.conversationId,
        query_message_id=request.context.queryMessageId,
        feedback=request.feedback.value,
        reason=dump_model(request.reason) if request.reason else None,
    )
    return api_response(data=None)


@app.post("/agent/v1/assistant/conversation/list")
def conversation_list(request: ConversationListRequest, _user=Depends(current_user)):
    data = list_conversations(request.userId, request.conversationId)
    return api_response(data=data, meta_uuid=request.conversationId)


@app.post("/agent/v1/assistant/chat/list")
def chat_list(request: ChatListRequest, _user=Depends(current_user)):
    data = list_chats(request.userId, request.conversationId, request.page, request.pageSize)
    return api_response(data=data, meta_uuid=request.conversationId)


@app.post("/agent/v1/knowledge/save")
def knowledge_save(request: KnowledgeSaveRequest, _user=Depends(require_admin)):
    data = write_markdown_knowledge(
        title=request.title,
        content=request.content,
        filename=request.filename,
        category=request.category,
        tags=request.tags,
        status=request.status,
        owner=request.owner,
        visibility=request.visibility,
        review_notes=request.reviewNotes,
    )
    return api_response(data=data)


@app.post("/agent/v1/knowledge/list")
def knowledge_list(_user=Depends(require_admin)):
    return api_response(data=list_markdown_knowledge())


@app.post("/agent/v1/knowledge/detail")
def knowledge_detail(request: KnowledgeDetailRequest, _user=Depends(require_admin)):
    try:
        return api_response(data=get_markdown_knowledge_detail(request.filename))
    except FileNotFoundError as exc:
        return api_response(data=None, code=404, des=str(exc))


@app.post("/agent/v1/knowledge/search")
def knowledge_search(request: KnowledgeSearchRequest, _user=Depends(require_admin)):
    results = retrieve_knowledge(request.query, request.topK)
    record_knowledge_hits(channel="search", query=request.query, results=results)
    return api_response(data=results)


@app.post("/agent/v1/knowledge/revision/list")
def knowledge_revision_list(request: KnowledgeRevisionListRequest, _user=Depends(require_admin)):
    return api_response(data=list_markdown_knowledge_revisions(request.filename, request.page, request.pageSize))


@app.post("/agent/v1/knowledge/status")
def knowledge_status(request: KnowledgeStatusRequest, _user=Depends(require_admin)):
    try:
        return api_response(data=change_markdown_knowledge_status(request.filename, request.status, request.reviewNotes))
    except FileNotFoundError as exc:
        return api_response(data=None, code=404, des=str(exc))


@app.post("/agent/v1/knowledge/gap/list")
def knowledge_gap_list(request: KnowledgeGapListRequest, _user=Depends(require_admin)):
    return api_response(data=list_markdown_knowledge_gaps(request.page, request.pageSize))


@app.post("/agent/v1/ops/dashboard")
def ops_dashboard(request: OpsDashboardRequest, _user=Depends(require_admin)):
    return api_response(
        data=get_ops_dashboard(
            start_date=request.startDate,
            end_date=request.endDate,
            user_id=request.userId,
            service=request.service,
            scene=request.scene,
        )
    )
