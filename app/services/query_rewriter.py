from app.core.llm import llm

REWRITER_SYSTEM = """You rewrite a customer's follow-up message into a standalone query for a knowledge-base search system.

Rules:
- Resolve pronouns and vague references using the conversation history ("it" -> "order ORD123", "that policy" -> "the refund policy").
- You may add retrieval keywords (product names, policy names, order IDs). Do NOT answer the question.
- If the message is already standalone, return it unchanged.
- Output ONLY the rewritten query text. No quotes, no explanation."""

def rewrite_query(query: str, history: list[dict], summary: str | None = None) -> str:
    if not history and not summary:
        return query
    system = REWRITER_SYSTEM
    if summary:
        system += f"\n\nConversation summary (use it to resolve references):\n{summary}"
    messages = [{"role": "system", "content": system}]
    for m in history[-6:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": f"Rewrite this for retrieval:\n{query}"})
    try:
        out = (llm.chat(messages, temperature=0.0).content or "").strip().strip('"')
        return out or query
    except Exception:
        return query  # rewriting must never break the pipeline