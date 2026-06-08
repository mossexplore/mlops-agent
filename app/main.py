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

from .agent import stream_chunks
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
    get_agent_trace,
    get_diagnostic_state,
    init_db,
    list_ab_experiments,
    list_chats,
    list_conversations,
    list_eval_cases,
    list_eval_runs,
    record_knowledge_hits,
    save_agent_trace,
    save_feedback,
    upsert_eval_case,
    upsert_conversation,
    upsert_diagnostic_state,
)
from .diagnostics import run_diagnostic_agent
from .knowledge import (
    change_markdown_knowledge_status,
    get_markdown_knowledge_detail,
    list_markdown_knowledge_gaps,
    list_markdown_knowledge,
    list_markdown_knowledge_revisions,
    retrieve_knowledge,
    should_use_local_knowledge,
    write_markdown_knowledge,
)
from .quality import (
    annotate_feedback,
    create_eval_case_from_feedback,
    create_or_update_experiment,
    get_quality_dashboard,
    get_quality_metrics,
    list_feedback_workspace,
    run_eval_suite,
)
from .runbooks import (
    change_runbook_status,
    get_runbook_detail,
    has_strong_runbook_match,
    list_runbook_workspace,
    retrieve_runbooks,
    save_runbook_workspace,
    should_use_runbook,
)
from .schemas import (
    ChatListRequest,
    ChatRequest,
    ConversationListRequest,
    EvalCaseFromFeedbackRequest,
    EvalCaseListRequest,
    EvalCaseSaveRequest,
    EvalRunListRequest,
    EvalRunRequest,
    ExperimentSaveRequest,
    FeedbackRequest,
    TraceDetailRequest,
    DiagnosticStateRequest,
    KnowledgeDetailRequest,
    KnowledgeGapListRequest,
    KnowledgeRevisionListRequest,
    KnowledgeSaveRequest,
    KnowledgeSearchRequest,
    KnowledgeStatusRequest,
    LoginRequest,
    OpsDashboardRequest,
    QualityFeedbackAnnotateRequest,
    QualityFeedbackListRequest,
    RunbookDetailRequest,
    RunbookListRequest,
    RunbookSaveRequest,
    RunbookStatusRequest,
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


def _serve_app(request: Request):
    """Serve the single-page console (client-side routing handles the view)."""
    redirect = require_page_session(request)
    if redirect:
        return redirect
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/")
def index(request: Request):
    return _serve_app(request)


@app.get("/knowledge")
def knowledge_page(request: Request):
    return _serve_app(request)


@app.get("/runbooks")
def runbooks_page(request: Request):
    return _serve_app(request)


@app.get("/ops")
def ops_page(request: Request):
    return _serve_app(request)


@app.get("/quality")
def quality_page(request: Request):
    return _serve_app(request)


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
    runbook_results = retrieve_runbooks(request.query, top_k=3)
    grounding_mode = "runbook" if request.groundingMode == "runbook" or has_strong_runbook_match(runbook_results) else "knowledge"
    query_message_id = str(uuid.uuid4())
    answer_message_id = str(uuid.uuid4())
    query_send_time = int(time.time() * 1000)
    previous_state = get_diagnostic_state(context.userId, context.conversationId)
    knowledge_results = retrieve_knowledge(request.query, top_k=5) if grounding_mode == "knowledge" else []
    if grounding_mode != "runbook":
        runbook_results = []
    if grounding_mode == "knowledge":
        record_knowledge_hits(
            channel="chat",
            query=request.query,
            results=knowledge_results,
            user_id=context.userId,
            conversation_id=context.conversationId,
            message_id=query_message_id,
        )
    diagnostic = run_diagnostic_agent(
        query=request.query,
        context=context,
        query_message_id=query_message_id,
        answer_message_id=answer_message_id,
        knowledge_results=knowledge_results if grounding_mode == "knowledge" and should_use_local_knowledge(request.query, knowledge_results) else [],
        runbook_results=runbook_results if grounding_mode == "runbook" and should_use_runbook(request.query, runbook_results) else [],
        previous_state=previous_state,
        need_deep_thinking=request.needDeepThinking,
        grounding_mode=grounding_mode,
    )
    answer = diagnostic["answer"]
    trace = diagnostic["trace"]
    save_agent_trace(trace, diagnostic["spans"])
    upsert_diagnostic_state(
        user_id=context.userId,
        conversation_id=context.conversationId,
        current_step=diagnostic["diagnosticState"]["currentStep"],
        summary=diagnostic["diagnosticState"]["summary"],
        facts=diagnostic["diagnosticState"]["facts"],
        open_questions=diagnostic["diagnosticState"]["openQuestions"],
        risk_level=diagnostic["diagnosticState"]["riskLevel"],
    )

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
                "traceId": trace["traceId"],
                "groundingMode": grounding_mode,
                "diagnosticState": diagnostic["diagnosticState"],
                "messageSendTime": int(time.time() * 1000),
                "querySendTime": query_send_time,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.035)
        add_chat(answer_message_id, context.userId, context.conversationId, "assistant", full_content, trace_id=trace["traceId"])

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/agent/v1/assistant/trace/detail")
def trace_detail(request: TraceDetailRequest, _user=Depends(current_user)):
    trace = get_agent_trace(request.traceId)
    if not trace:
        return api_response(data=None, code=404, des="Trace not found")
    return api_response(data=trace)


@app.post("/agent/v1/assistant/diagnostic/state")
def diagnostic_state(request: DiagnosticStateRequest, _user=Depends(current_user)):
    return api_response(data=get_diagnostic_state(request.userId, request.conversationId))


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


@app.post("/agent/v1/runbook/list")
def runbook_list(request: RunbookListRequest, _user=Depends(require_admin)):
    return api_response(
        data=list_runbook_workspace(
            status=request.status,
            service=request.service,
            scenario=request.scenario,
            query=request.query,
        )
    )


@app.post("/agent/v1/runbook/detail")
def runbook_detail(request: RunbookDetailRequest, _user=Depends(require_admin)):
    data = get_runbook_detail(request.runbookId)
    if not data:
        return api_response(data=None, code=404, des="Runbook not found")
    return api_response(data=data)


@app.post("/agent/v1/runbook/save")
def runbook_save(request: RunbookSaveRequest, _user=Depends(require_admin)):
    try:
        return api_response(
            data=save_runbook_workspace(
                runbook_id=request.runbookId,
                title=request.title,
                service=request.service,
                scenario=request.scenario,
                severity=request.severity,
                status=request.status,
                owner=request.owner,
                version=request.version,
                trigger=request.trigger,
                summary=request.summary,
                verification=request.verification,
                escalation=request.escalation,
                risk_controls=request.riskControls,
                tags=request.tags,
                related_knowledge=request.relatedKnowledge,
                steps=[dump_model(step) for step in request.steps],
            )
        )
    except ValueError as exc:
        return api_response(data=None, code=400, des=str(exc))


@app.post("/agent/v1/runbook/status")
def runbook_status(request: RunbookStatusRequest, _user=Depends(require_admin)):
    try:
        data = change_runbook_status(request.runbookId, request.status)
    except ValueError as exc:
        return api_response(data=None, code=400, des=str(exc))
    if not data:
        return api_response(data=None, code=404, des="Runbook not found")
    return api_response(data=data)


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


@app.post("/agent/v1/quality/dashboard")
def quality_dashboard(_user=Depends(require_admin)):
    return api_response(data=get_quality_dashboard())


@app.post("/agent/v1/quality/metrics")
def quality_metrics(_user=Depends(require_admin)):
    return api_response(data=get_quality_metrics())


@app.post("/agent/v1/quality/feedback/list")
def quality_feedback_list(request: QualityFeedbackListRequest, _user=Depends(require_admin)):
    return api_response(data=list_feedback_workspace(request.status, request.page, request.pageSize))


@app.post("/agent/v1/quality/feedback/annotate")
def quality_feedback_annotate(request: QualityFeedbackAnnotateRequest, _user=Depends(require_admin)):
    try:
        data = annotate_feedback(
            answer_message_id=request.answerMessageId,
            user_id=request.userId,
            conversation_id=request.conversationId,
            quality_reason=request.qualityReason,
            status=request.status,
            annotation=request.annotation,
            reviewer=request.reviewer,
        )
        return api_response(data=data)
    except ValueError as exc:
        return api_response(data=None, code=400, des=str(exc))


@app.post("/agent/v1/quality/eval-case/save")
def quality_eval_case_save(request: EvalCaseSaveRequest, _user=Depends(require_admin)):
    return api_response(
        data=upsert_eval_case(
            case_id=request.caseId,
            title=request.title,
            query=request.query,
            expected_answer=request.expectedAnswer,
            required_steps=request.requiredSteps,
            forbidden_content=request.forbiddenContent,
            tags=request.tags,
            status=request.status,
        )
    )


@app.post("/agent/v1/quality/eval-case/from-feedback")
def quality_eval_case_from_feedback(request: EvalCaseFromFeedbackRequest, _user=Depends(require_admin)):
    try:
        return api_response(
            data=create_eval_case_from_feedback(
                answer_message_id=request.answerMessageId,
                user_id=request.userId,
                conversation_id=request.conversationId,
                title=request.title,
                expected_answer=request.expectedAnswer,
                required_steps=request.requiredSteps or None,
                forbidden_content=request.forbiddenContent or None,
                tags=request.tags or None,
            )
        )
    except ValueError as exc:
        return api_response(data=None, code=404, des=str(exc))


@app.post("/agent/v1/quality/eval-case/list")
def quality_eval_case_list(request: EvalCaseListRequest, _user=Depends(require_admin)):
    return api_response(data=list_eval_cases(request.status, request.page, request.pageSize))


@app.post("/agent/v1/quality/eval/run")
def quality_eval_run(request: EvalRunRequest, _user=Depends(require_admin)):
    return api_response(
        data=run_eval_suite(
            name=request.name,
            variant=request.variant,
            prompt_version=request.promptVersion,
            retrieval_threshold=request.retrievalThreshold,
            model=request.model,
            case_ids=request.caseIds or None,
        )
    )


@app.post("/agent/v1/quality/eval/run/list")
def quality_eval_run_list(request: EvalRunListRequest, _user=Depends(require_admin)):
    return api_response(data=list_eval_runs(request.page, request.pageSize))


@app.post("/agent/v1/quality/experiment/save")
def quality_experiment_save(request: ExperimentSaveRequest, _user=Depends(require_admin)):
    return api_response(
        data=create_or_update_experiment(
            experiment_id=request.experimentId,
            name=request.name,
            variants=request.variants,
            traffic_split=request.trafficSplit,
            primary_metric=request.primaryMetric,
            status=request.status,
            notes=request.notes,
        )
    )


@app.post("/agent/v1/quality/experiment/list")
def quality_experiment_list(_user=Depends(require_admin)):
    return api_response(data=list_ab_experiments())
