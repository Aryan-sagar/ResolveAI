import time
from openai import OpenAI
from app.config import settings

PROVIDERS = {
    "openai":     "https://api.openai.com/v1",
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq":       "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama":     "http://localhost:11434/v1",
}

def _key_for(provider: str) -> str:
    return {"gemini": settings.gemini_api_key, "groq": settings.groq_api_key,
            "openai": settings.openai_api_key, "openrouter": settings.openrouter_api_key,
            }.get(provider, "")

def _retryable(e) -> bool:
    status = getattr(e, "status_code", None)
    if status in (429, 500, 502, 503):
        return True
    return type(e).__name__ in ("APIConnectionError", "APITimeoutError")

class LLMClient:
    """One client for every provider — they all speak the OpenAI chat-completions
    protocol, so swapping is env-only. Free tiers rate-limit aggressively, so every
    call retries with exponential backoff on 429/5xx."""

    def __init__(self, provider: str, model: str):
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; choices: {list(PROVIDERS)}")
        key = _key_for(provider)
        if provider != "ollama" and not key:
            raise RuntimeError(f"missing API key for provider '{provider}' — set it in .env")
        self.provider, self.model = provider, model
        self.client = OpenAI(api_key=key or "ollama", base_url=PROVIDERS[provider])

    def chat(self, messages, tools=None, json_mode=False, temperature=0.2, max_retries=4):
        kwargs = dict(model=self.model, messages=messages, temperature=temperature)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                return resp.choices[0].message
            except Exception as e:
                if not _retryable(e) or attempt == max_retries - 1:
                    raise
                time.sleep(min(2 ** attempt + 1, 30))   # 2s, 3s, 5s, 9s
        raise RuntimeError("unreachable")

llm = LLMClient(settings.llm_provider, settings.llm_model)

_jp = settings.judge_provider or settings.llm_provider
_jm = settings.judge_model or settings.llm_model
judge_llm = llm if (_jp, _jm) == (settings.llm_provider, settings.llm_model) \
            else LLMClient(_jp, _jm)