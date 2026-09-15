from app.config import settings
from app.core.llm import llm
from app.db.session import SessionLocal
from app.db.models import Conversation, Message

SUMMARY_SYSTEM = """You maintain a rolling summary of a customer support conversation for an assistant with a limited context window.

Capture, compactly:
- entities: order IDs, ticket IDs, amounts, dates
- what the customer wants and what they have already been told
- actions taken (tickets created, refunds/cancellations proposed or approved) and anything pending

Rules:
- If a previous summary is provided, merge it with the new messages into ONE updated summary.
- Facts only, no pleasantries. Under 150 words.
- Output ONLY the summary text."""

def maybe_summarize(conversation_id: str) -> tuple[str | None, int]:
    """Fold older turns into the rolling summary once unsummarized history exceeds
    the trigger. Returns (summary, watermark_message_id). Never raises — memory
    compression must not break the request path."""
    summary, watermark = None, 0
    db = SessionLocal()
    try:
        conv = db.get(Conversation, conversation_id)
        if not conv:
            return None, 0
        summary, watermark = conv.summary, conv.summarized_up_to or 0
        msgs = (db.query(Message)
                  .filter(Message.conversation_id == conversation_id, Message.id > watermark)
                  .order_by(Message.id).all())
        if len(msgs) < settings.summary_trigger_messages:
            return summary, watermark
        to_fold = msgs[:-settings.summary_keep_recent]
        transcript = "\n".join(f"{m.role}: {m.content}" for m in to_fold)
        user = (f"Previous summary:\n{summary}\n\n" if summary else "") + \
               f"New messages to fold in:\n{transcript}"
        new = (llm.chat([{"role": "system", "content": SUMMARY_SYSTEM},
                         {"role": "user", "content": user}], temperature=0.0).content or "").strip()
        if new:
            conv.summary, conv.summarized_up_to = new, to_fold[-1].id
            db.commit()
            return new, to_fold[-1].id
        return summary, watermark
    except Exception as e:
        print(f"[memory] summarization skipped: {e}")
        db.rollback()
        return summary, watermark
    finally:
        db.close()
        