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


def api_response(data: Any = None, code: int = 0, des: str = "success", meta_uuid: Optional[str] = None) -> Dict[str, Any]:
    import uuid

    return {
        "version": "1.0",
        "meta": {"uuid": meta_uuid or str(uuid.uuid4())},
        "result": {"code": code, "des": des, "data": data},
    }
