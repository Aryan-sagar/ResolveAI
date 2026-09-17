import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest
from app.services.orchestrator import run_chat, run_chat_events
from app.db.session import SessionLocal
from app.db.models import Message

router = APIRouter(prefix="/api")

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return run_chat(req.query, req.conversation_id, req.user_id, req.tenant_id, req.role)

@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    def events():
        for kind, payload in run_chat_events(req.query, req.conversation_id, req.user_id,
                                             req.tenant_id, req.role, stream=True):
            if kind == "delta":
                data = {"text": payload}
            elif isinstance(payload, dict):
                data = payload
            else:
                data = {"stage": payload}
            yield f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

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
