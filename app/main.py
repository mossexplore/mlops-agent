import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent import build_answer, stream_chunks
from .database import add_chat, init_db, list_chats, list_conversations, save_feedback, upsert_conversation
from .knowledge import (
    build_grounded_answer,
    get_markdown_knowledge_detail,
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
    KnowledgeRevisionListRequest,
    KnowledgeSaveRequest,
    KnowledgeSearchRequest,
    api_response,
)


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Wise MLOps Agent", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def dump_model(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/knowledge")
def knowledge_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "knowledge.html")


@app.post("/agent/v1/assistant/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    context = request.context
    query_message_id = str(uuid.uuid4())
    answer_message_id = str(uuid.uuid4())
    query_send_time = int(time.time() * 1000)
    knowledge_results = retrieve_knowledge(request.query, top_k=5)
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
def feedback(request: FeedbackRequest):
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
def conversation_list(request: ConversationListRequest):
    data = list_conversations(request.userId, request.conversationId)
    return api_response(data=data, meta_uuid=request.conversationId)


@app.post("/agent/v1/assistant/chat/list")
def chat_list(request: ChatListRequest):
    data = list_chats(request.userId, request.conversationId, request.page, request.pageSize)
    return api_response(data=data, meta_uuid=request.conversationId)


@app.post("/agent/v1/knowledge/save")
def knowledge_save(request: KnowledgeSaveRequest):
    data = write_markdown_knowledge(request.title, request.content, request.filename)
    return api_response(data=data)


@app.post("/agent/v1/knowledge/list")
def knowledge_list():
    return api_response(data=list_markdown_knowledge())


@app.post("/agent/v1/knowledge/detail")
def knowledge_detail(request: KnowledgeDetailRequest):
    try:
        return api_response(data=get_markdown_knowledge_detail(request.filename))
    except FileNotFoundError as exc:
        return api_response(data=None, code=404, des=str(exc))


@app.post("/agent/v1/knowledge/search")
def knowledge_search(request: KnowledgeSearchRequest):
    return api_response(data=retrieve_knowledge(request.query, request.topK))


@app.post("/agent/v1/knowledge/revision/list")
def knowledge_revision_list(request: KnowledgeRevisionListRequest):
    return api_response(data=list_markdown_knowledge_revisions(request.filename, request.page, request.pageSize))
