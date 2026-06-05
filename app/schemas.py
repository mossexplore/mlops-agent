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


class OpsDashboardRequest(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    userId: Optional[str] = None
    service: Optional[str] = None
    scene: Optional[str] = None


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
