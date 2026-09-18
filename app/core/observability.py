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

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
except Exception as e:
    logger.warning("langfuse init failed, tracing disabled: %s", e)

if not _client:
    logger.info("langfuse disabled (no keys) — everything still works, just untraced")

# Whether finish() should block on client.flush().
# Keep True for local/demo so traces show up instantly.
_SYNC_FLUSH = getattr(settings, "langfuse_sync_flush", False)


def _clip(obj, limit: int = 2000):
    """Best-effort JSON-safe, size-capped view of obj."""
    try:
        s = json.dumps(obj, default=str)
    except Exception:
        return {"error": "unserializable"}

    if len(s) <= limit:
        return obj

    return {
        "truncated": True,
        "original_length": len(s),
        "preview": s[:limit],
    }


_current_trace: ContextVar = ContextVar(
    "langfuse_trace",
    default=None,
)


class Observability:
    """Langfuse v4 tracing with a no-op fallback.

    Observability must never take down the request path.
    """

    def __init__(self, client):
        self.client = client

    @property
    def trace(self):
        return _current_trace.get()

    @property
    def trace_id(self):
        trace = self.trace
        return trace.trace_id if trace else None

    def start(self, name, user_id, session_id, input_data, metadata=None):
        if not self.client:
            return

        try:
            trace = self.client.start_observation(
                name=name,
                as_type="span",
                input=_clip(input_data),
                metadata=_clip({
                    **(metadata or {}),
                    "user_id": user_id,
                    "session_id": session_id,
                }),
            )

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

        try:
            child = trace.start_observation(
                name=name,
                as_type="span",
                metadata=_clip(metadata or {}),
            )

            yield

        except Exception:
            logger.debug(
                "span '%s' logging failed",
                name,
                exc_info=True,
            )

        finally:
            try:
                if "child" in locals():
                    child.end()
            except Exception:
                logger.debug(
                    "span '%s' finish failed",
                    name,
                    exc_info=True,
                )

    def tool(self, name, arguments, result):
        trace = self.trace

        if not trace:
            return

        try:
            tool_obs = trace.start_observation(
                name=f"tool:{name}",
                as_type="tool",
                input=_clip(arguments),
                output=_clip(result),
            )
            tool_obs.end()

        except Exception:
            logger.debug(
                "tool span '%s' logging failed",
                name,
                exc_info=True,
            )

    def finish(self, output, metadata=None):
        trace = self.trace

        if not trace:
            return

        try:
            trace.update(
                output=_clip(output),
                metadata=_clip(metadata or {}),
            )
            trace.end()

            if _SYNC_FLUSH:
                self.client.flush()

        except Exception:
            logger.debug(
                "trace finish failed",
                exc_info=True,
            )

        finally:
            _current_trace.set(None)

    def score(self, trace_id, name, value):
        if not self.client:
            return

        try:
            self.client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
            )
        except Exception:
            logger.debug(
                "score '%s' failed",
                name,
                exc_info=True,
            )


obs = Observability(_client)