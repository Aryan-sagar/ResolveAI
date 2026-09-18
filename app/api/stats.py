from fastapi import APIRouter
from app.db.session import SessionLocal
from app.db.models import Message, ToolCallRecord
from app.core.llm import usage_totals
from app.services import semantic_cache

router = APIRouter(prefix="/api")

@router.get("/stats")
def stats():
    db = SessionLocal()
    asst = (db.query(Message).filter(Message.role == "assistant")
              .order_by(Message.id.desc()).limit(500).all())
    lats = sorted(m.latency_ms or 0 for m in asst)
    p = lambda q: lats[round((len(lats) - 1) * q / 100)] if lats else 0
    fb_up = db.query(Message).filter(Message.feedback == 1).count()
    fb_down = db.query(Message).filter(Message.feedback == -1).count()
    tool_rows = (db.query(ToolCallRecord).order_by(ToolCallRecord.id.desc()).limit(200).all())
    tools_by = {}
    for r in tool_rows:
        tools_by.setdefault(r.tool_name, {}).setdefault(r.status, 0)
        tools_by[r.tool_name][r.status] += 1
    queries = db.query(Message).filter(Message.role == "user").count()
    db.close()
    hits, misses = semantic_cache.counters["hits"], semantic_cache.counters["misses"]
    return {"queries": queries,
            "latency_ms": {"avg": int(sum(lats) / len(lats)) if lats else 0,
                           "p50": p(50), "p95": p(95)},
            "feedback": {"up": fb_up, "down": fb_down},
            "cache": {"hits": hits, "misses": misses,
                      "hit_rate": round(hits / (hits + misses), 3) if hits + misses else None},
            "tools": tools_by,
            "recent_tool_calls": [{"tool": r.tool_name, "status": r.status, "risk": r.risk_level,
                                   "at": str(r.created_at)} for r in tool_rows[:20]],
            "token_usage": {k: dict(v) for k, v in usage_totals.items()},
            "latency_history": [m.latency_ms for m in reversed(asst)][:100]}