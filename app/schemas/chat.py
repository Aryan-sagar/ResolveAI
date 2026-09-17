from typing import Optional, Any

from pydantic import BaseModel, Field


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
    arguments: dict = Field(default_factory=dict)
    result: Optional[Any] = None
    reason: Optional[str] = None
    action_id: Optional[str] = None


class ProposedAction(BaseModel):
    action_id: str
    name: str
    arguments: dict


class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int  # 1 helpful, -1 not helpful


class RetrievedChunk(BaseModel):
    source: str
    score: Optional[float] = None
    content: str = ""


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    intent: Optional[str] = None
    rewritten_query: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    invalid_citations: list[int] = Field(default_factory=list)
    retrieved: list[RetrievedChunk] = Field(default_factory=list)
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    requires_approval: bool = False
    proposed_action: Optional[ProposedAction] = None
    latency_ms: int = 0
    timings: dict[str, int] = Field(default_factory=dict)
    guardrail: Optional[str] = None
    ticket_enrichment: Optional[dict] = None
    memory: dict = Field(default_factory=dict)