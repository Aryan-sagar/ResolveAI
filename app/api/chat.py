from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest
from app.services.orchestrator import run_chat
from app.db.session import SessionLocal
from app.db.models import Message

router = APIRouter(prefix="/api")

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return run_chat(req.query, req.conversation_id, req.user_id, req.tenant_id, req.role)

@router.post("/feedback")
def feedback(req: FeedbackRequest):
    db = SessionLocal()
    msg = db.query(Message).filter(Message.conversation_id == req.conversation_id,
                                    Message.role == "assistant").order_by(Message.id.desc()).first()
    if msg:
        msg.feedback = req.rating
        db.commit()
    db.close()
    return {"ok": bool(msg)}
