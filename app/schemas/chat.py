from typing import Optional, Any
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    user_id: str = "user_1"
    tenant_id: str = "acme"
    role: str = "customer"  # customer | agent | admin

class Citation(BaseModel):
    source: str
    chunk_id: Optional[str] = None
    score: Optional[float] = None

class ToolCallInfo(BaseModel):
    name: str
    status: str
    action_id: Optional[str] = None

class ProposedAction(BaseModel):
    action_id: str
    name: str
    arguments: dict

class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    intent: Optional[str] = None
    citations: list[Citation] = []
    tool_calls: list[ToolCallInfo] = []
    requires_approval: bool = False
    proposed_action: Optional[ProposedAction] = None
    latency_ms: int = 0
    guardrail: Optional[str] = None

class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int  # 1 helpful, -1 not helpful