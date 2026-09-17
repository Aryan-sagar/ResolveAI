import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from contextlib import contextmanager
from app.config import settings

logger = logging.getLogger(__name__)

_client = None
try:
    if settings.langfuse_public_key:
        from langfuse import Langfuse
        _client = Langfuse(public_key=settings.langfuse_public_key,
                            secret_key=settings.langfuse_secret_key,
                            host=settings.langfuse_host)
except Exception as e:
    logger.warning("langfuse init failed, tracing disabled: %s", e)

if not _client:
    logger.info("langfuse disabled (no keys) — everything still works, just untraced")

# Whether finish() should block on client.flush(). Keep True for local/demo
# so traces show up instantly in the UI; set False in prod so requests
# don't pay the network round-trip cost of a synchronous flush.
_SYNC_FLUSH = getattr(settings, "langfuse_sync_flush", False)


def _clip(obj, limit: int = 2000):
    """Best-effort JSON-safe, size-capped view of obj.

    Serializes first, then truncates the *string* if needed and returns a
    small wrapper — never re-parses a truncated string as JSON (which was
    the bug: slicing valid JSON almost always yields invalid JSON, so the
    old version silently fell back to {"error": "unserializable"} even for
    perfectly fine objects that were merely long).
    """
    try:
        s = json.dumps(obj, default=str)
    except Exception:
        return {"error": "unserializable"}
    if len(s) <= limit:
        return obj
    return {"truncated": True, "original_length": len(s), "preview": s[:limit]}


_current_trace: ContextVar = ContextVar("langfuse_trace", default=None)


class Observability:
    """Langfuse tracing with a no-op fallback. Every method swallows exceptions:
    observability must never take the request path down."""

    def __init__(self, client):
        self.client = client

    @property
    def trace(self):
        return _current_trace.get()

    @property
    def trace_id(self):
        t = self.trace
        return t.id if t else None

    def start(self, name, user_id, session_id, input_data, metadata=None):
        if not self.client:
            return
        try:
            trace = self.client.trace(name=name, user_id=user_id,
                                       session_id=session_id, input=input_data,
                                       metadata=_clip(metadata or {}))
            _current_trace.set(trace)
        except Exception as e:
            logger.warning("trace start failed: %s", e)
            _current_trace.set(None)

    @contextmanager
    def span(self, name, metadata=None):
        trace = self.trace
        if not trace:
            yield
            return
        t0 = datetime.now(timezone.utc)
        try:
            yield
        finally:
            try:
                trace.span(name=name, start_time=t0,
                           end_time=datetime.now(timezone.utc),
                           metadata=_clip(metadata or {}))
            except Exception:
                logger.debug("span '%s' logging failed", name, exc_info=True)

    def tool(self, name, arguments, result):
        trace = self.trace
        if not trace:
            return
        try:
            trace.span(name=f"tool:{name}",
                       metadata=_clip({"arguments": arguments, "result": result}))
        except Exception:
            logger.debug("tool span '%s' logging failed", name, exc_info=True)

    def finish(self, output, metadata=None):
        trace = self.trace
        if not trace:
            return
        try:
            trace.update(output=output, metadata=_clip(metadata or {}))
            if _SYNC_FLUSH:
                self.client.flush()
        except Exception:
            logger.debug("trace finish failed", exc_info=True)
        finally:
            _current_trace.set(None)

    def score(self, trace_id, name, value):
        if not self.client:
            return
        try:
            self.client.score(trace_id=trace_id, name=name, value=value)
        except Exception:
            logger.debug("score '%s' failed", name, exc_info=True)


obs = Observability(_client)