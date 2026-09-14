from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass

def utcnow(): return datetime.now(timezone.utc)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(512))
    doc_type: Mapped[str] = mapped_column(String(50))
    tenant_id: Mapped[str] = mapped_column(String(50), index=True)
    access_level: Mapped[str] = mapped_column(String(20))  # public | internal
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    qdrant_id: Mapped[str] = mapped_column(String(64), index=True)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    tenant_id: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    feedback: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class ToolCallRecord(Base):
    __tablename__ = "tool_calls"   # this is your audit log
    id: Mapped[int] = mapped_column(primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(100))
    arguments: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))  # started|success|error|pending_approval|rejected|denied
    response: Mapped[dict] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20))
    approved_by: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)