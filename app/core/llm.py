import contextvars
import threading
import time
import types
from collections import defaultdict
from openai import OpenAI
from app.config import settings
from app.core.mock_llm import MockLLMClient

PROVIDERS = {
    "mock":        None,
    "openai":     "https://api.openai.com/v1",
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq":       "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama":     "http://localhost:11434/v1",
}

def _key_for(provider):
    return {"gemini": settings.gemini_api_key, "groq": settings.groq_api_key,
            "openai": settings.openai_api_key, "openrouter": settings.openrouter_api_key}.get(provider, "")

_sink = contextvars.ContextVar("usage_sink", default=None)
usage_totals = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0})
_totals_lock = threading.Lock()

def set_usage_sink(sink):
    return _sink.set(sink)

def reset_usage_sink(token):
    _sink.reset(token)

def _record_usage(model, usage):
    if not usage:
        return
    entry = {"model": model,
             "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
             "completion_tokens": getattr(usage, "completion_tokens", 0) or 0}
    sink = _sink.get()
    if sink is not None:
        sink.append(entry)                      # per-request attribution
    with _totals_lock:                          # process-wide aggregate for the dashboard
        t = usage_totals[model]
        t["prompt_tokens"] += entry["prompt_tokens"]
        t["completion_tokens"] += entry["completion_tokens"]
        t["calls"] += 1

def _retryable(e):
    status = getattr(e, "status_code", None)
    if status in (429, 500, 502, 503):
        return True
    return type(e).__name__ in ("APIConnectionError", "APITimeoutError")

class LLMClient:
    def __init__(self, provider, model):
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; choices: {list(PROVIDERS)}")

        key = _key_for(provider)
        if provider != "ollama" and not key:
            raise RuntimeError(f"missing API key for provider '{provider}'")
        self.provider, self.model = provider, model
        self.client = OpenAI(api_key=key or "ollama", base_url=PROVIDERS[provider])

    def _create(self, **kwargs):
        for attempt in range(4):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                if not _retryable(e) or attempt == 3:
                    raise
                time.sleep(min(2 ** attempt + 1, 30))

    def chat(self, messages, tools=None, json_mode=False, temperature=0.2, model=None):
        kwargs = dict(model=model or self.model, messages=messages, temperature=temperature)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._create(**kwargs)
        _record_usage(kwargs["model"], resp.usage)
        return resp.choices[0].message

    def chat_stream(self, messages, tools=None, temperature=0.2, model=None):
        """Generator: yields ('delta', text) as tokens arrive; RETURNS the assembled
        message (captured by callers via `msg = yield from ...`). Tool-call fragments
        accumulate across stream chunks. Retries apply to connection only — a stream
        that breaks mid-flight is not retried, since partial output may already have
        been forwarded to the client."""
        kwargs = dict(model=model or self.model, messages=messages,
                      temperature=temperature, stream=True)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        stream = self._create(**kwargs)
        content, tc_acc = [], {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content.append(delta.content)
                yield ("delta", delta.content)
            for tc in (delta.tool_calls or []):
                idx = tc.index if tc.index is not None else 0
                acc = tc_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                if tc.id:
                    acc["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        acc["name"] += tc.function.name
                    if tc.function.arguments:
                        acc["args"] += tc.function.arguments
        tool_calls = ([types.SimpleNamespace(id=a["id"],
                                              function=types.SimpleNamespace(name=a["name"],
                                                                             arguments=a["args"]))
                       for _, a in sorted(tc_acc.items())] or None)
        return types.SimpleNamespace(content="".join(content) or None, tool_calls=tool_calls)

if settings.llm_provider == "mock":
    from app.core.mock_llm import MockLLMClient
    llm = MockLLMClient()
    judge_llm = MockLLMClient()
else:
    llm = LLMClient(settings.llm_provider, settings.llm_model)
    _jp = settings.judge_provider or settings.llm_provider
    _jm = settings.judge_model or settings.llm_model
    judge_llm = llm if (_jp, _jm) == (settings.llm_provider, settings.llm_model) \
                else LLMClient(_jp, _jm)