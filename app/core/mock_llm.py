import json, re, types

def _msg(content=None, tool_calls=None):
    return types.SimpleNamespace(content=content, tool_calls=tool_calls)

def _tc(name, arguments):
    return types.SimpleNamespace(
        id=f"call_{name}",
        function=types.SimpleNamespace(name=name, arguments=json.dumps(arguments)))

class MockLLMClient:
    provider = "mock"

    def __init__(self, model="mock"):
        self.model = model

    def chat(self, messages, tools=None, json_mode=False, temperature=0.2, model=None):
        system = messages[0]["content"] if messages else ""
        last_user = next((m["content"] for m in reversed(messages)
                          if m["role"] == "user"), "")
        s = system.lower()

        # router (classify sends json_mode=True)
        if "classify customer support queries" in s:
            q = last_user.lower()
            m = re.search(r"ORD\d+", last_user)
            if any(w in q for w in ("ignore previous", "reveal your", "developer mode", "disregard")):
                out = {"intent": "unsafe", "requires_rag": False, "requires_api": False,
                       "risk_level": "high", "entities": {}}
            elif "cancel" in q and m:
                out = {"intent": "cancel_request", "requires_rag": False, "requires_api": True,
                       "risk_level": "high", "entities": {"order_id": m.group()}}
            elif "refund" in q and m:
                out = {"intent": "refund_request", "requires_rag": True, "requires_api": True,
                       "risk_level": "high", "entities": {"order_id": m.group()}}
            elif m:
                out = {"intent": "order_status", "requires_rag": False, "requires_api": True,
                       "risk_level": "low", "entities": {"order_id": m.group()}}
            else:
                out = {"intent": "policy_question", "requires_rag": True, "requires_api": False,
                       "risk_level": "low", "entities": {}}
            return _msg(content=json.dumps(out))

        # rewriter: pass through
        if "rewrite a customer" in s:
            return _msg(content=last_user)

        # judges (defensive — CI and load tests don't use them)
        if json_mode:
            if "decompose" in s:
                return _msg(content=json.dumps({"claims": []}))
            if "rate 1-5" in s:
                return _msg(content=json.dumps({"score": 4}))
            if "retrieved chunk" in s:
                return _msg(content=json.dumps({"chunks": [{"index": 1, "relevant": True}]}))
            return _msg(content=json.dumps({}))

        # generation with tools: one tool round for order queries, then final
        if tools:
            tool_seen = any(m.get("role") == "tool" for m in messages)
            m = re.search(r"ORD\d+", last_user)
            if m and not tool_seen:
                return _msg(tool_calls=[_tc("get_order_status", {"order_id": m.group()})])
            cited = "[1]" if "### retrieved context" in s else ""
            return _msg(content=f"Mock grounded answer. {cited}".strip())

        return _msg(content="Mock answer.")

    def chat_stream(self, messages, tools=None, temperature=0.2, model=None):
        """Generator mirror of LLMClient.chat_stream: yields ('delta', text) chunks as
        they're produced, and RETURNS the assembled message — callers capture it via
        `msg = yield from llm.chat_stream(...)`, same as the real client. Reuses .chat()
        for the actual mock response logic so routing/tool behavior stays identical
        between streaming and non-streaming paths; only the delivery is chunked here."""
        result = self.chat(messages, tools=tools, temperature=temperature, model=model)

        if result.tool_calls:
            # real providers emit no content deltas on a tool-call turn; match that
            return result

        content = result.content or ""
        words = content.split(" ")
        for i, word in enumerate(words):
            piece = word if i == 0 else " " + word
            yield ("delta", piece)

        return _msg(content=content, tool_calls=None)


if __name__ == "__main__":
    # quick manual check: python -m app.core.mock_llm
    client = MockLLMClient()
    print(client.chat([{"role": "user", "content": "hello"}]).content)