from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    userId: str
    conversationId: str
    service: str
    scene: str
    title: str


class ChatRequest(BaseModel):
    query: str
    model: Optional[str] = None
    needDeepThinking: int = 0
    prompt: Optional[str] = None
    context: ChatContext


class FeedbackValue(str, Enum):
    like = "like"
    unlike = "unlike"
    none = "NONE"


class FeedbackReason(BaseModel):
    feedbackInfo: Optional[str] = None
    feedbackInfoTypes: List[str] = Field(default_factory=list)


class FeedbackContext(BaseModel):
    userId: str
    conversationId: str
    messageId: str
    queryMessageId: Optional[str] = None


class FeedbackRequest(BaseModel):
    feedback: FeedbackValue
    reason: Optional[FeedbackReason] = None
    context: FeedbackContext


class ConversationListRequest(BaseModel):
    userId: str
    conversationId: Optional[str] = None


class ChatListRequest(BaseModel):
    userId: str
    conversationId: str
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=100)


class TraceDetailRequest(BaseModel):
    traceId: str = Field(min_length=1)


class DiagnosticStateRequest(BaseModel):
    userId: str
    conversationId: str


class KnowledgeSaveRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    filename: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = None
    owner: Optional[str] = None
    visibility: Optional[str] = None
    reviewNotes: Optional[str] = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    topK: int = Field(default=5, ge=1, le=10)


class KnowledgeRevisionListRequest(BaseModel):
    filename: Optional[str] = None
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class KnowledgeDetailRequest(BaseModel):
    filename: str = Field(min_length=1)


class KnowledgeStatusRequest(BaseModel):
    filename: str = Field(min_length=1)
    status: str
    reviewNotes: Optional[str] = None


class KnowledgeGapListRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class RunbookStepRequest(BaseModel):
    stepId: Optional[str] = None
    order: Optional[int] = Field(default=None, ge=1)
    title: str = Field(min_length=1)
    actionType: str = "check"
    instruction: str = Field(min_length=1)
    evidenceRequired: Optional[str] = None
    toolName: Optional[str] = None
    expectedResult: Optional[str] = None
    riskLevel: str = "low"


class RunbookListRequest(BaseModel):
    status: Optional[str] = None
    service: Optional[str] = None
    scenario: Optional[str] = None
    query: Optional[str] = None


class RunbookDetailRequest(BaseModel):
    runbookId: str = Field(min_length=1)


class RunbookSaveRequest(BaseModel):
    runbookId: Optional[str] = None
    title: str = Field(min_length=1)
    service: str = "Wise"
    scenario: str = "模型任务"
    severity: str = "P2"
    status: str = "draft"
    owner: Optional[str] = None
    version: str = "v1"
    trigger: Optional[str] = None
    summary: Optional[str] = None
    verification: Optional[str] = None
    escalation: Optional[str] = None
    riskControls: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    relatedKnowledge: List[str] = Field(default_factory=list)
    steps: List[RunbookStepRequest] = Field(default_factory=list)


class RunbookStatusRequest(BaseModel):
    runbookId: str = Field(min_length=1)
    status: str


class OpsDashboardRequest(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    userId: Optional[str] = None
    service: Optional[str] = None
    scene: Optional[str] = None


class QualityFeedbackListRequest(BaseModel):
    status: Optional[str] = None
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class QualityFeedbackAnnotateRequest(BaseModel):
    answerMessageId: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    conversationId: str = Field(min_length=1)
    qualityReason: str = Field(min_length=1)
    status: str = "open"
    annotation: Optional[str] = None
    reviewer: Optional[str] = None


class EvalCaseSaveRequest(BaseModel):
    caseId: Optional[str] = None
    title: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expectedAnswer: Optional[str] = None
    requiredSteps: List[str] = Field(default_factory=list)
    forbiddenContent: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    status: str = "active"


class EvalCaseFromFeedbackRequest(BaseModel):
    answerMessageId: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    conversationId: str = Field(min_length=1)
    title: Optional[str] = None
    expectedAnswer: Optional[str] = None
    requiredSteps: List[str] = Field(default_factory=list)
    forbiddenContent: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class EvalCaseListRequest(BaseModel):
    status: Optional[str] = "active"
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=200)


class EvalRunRequest(BaseModel):
    name: str = Field(default="baseline quality run", min_length=1)
    variant: str = "baseline"
    promptVersion: Optional[str] = None
    retrievalThreshold: Optional[float] = None
    model: Optional[str] = None
    caseIds: List[str] = Field(default_factory=list)


class EvalRunListRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class ExperimentSaveRequest(BaseModel):
    experimentId: Optional[str] = None
    name: str = Field(min_length=1)
    status: str = "draft"
    variants: List[str] = Field(default_factory=list)
    trafficSplit: Dict[str, float] = Field(default_factory=dict)
    primaryMetric: str = "satisfactionRate"
    notes: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def api_response(data: Any = None, code: int = 0, des: str = "success", meta_uuid: Optional[str] = None) -> Dict[str, Any]:
    import uuid

    return {
        "version": "1.0",
        "meta": {"uuid": meta_uuid or str(uuid.uuid4())},
        "result": {"code": code, "des": des, "data": data},
    }
