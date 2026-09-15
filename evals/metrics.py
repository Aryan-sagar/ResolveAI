"""RAGAS-style metrics with a custom judge.

Why custom instead of the ragas package: per-claim debuggability (you see WHICH
claim broke faithfulness), fewer judge calls (2 per question, not 4+), and no
langchain version pinning. Definitions follow the RAGAS methodology:
- faithfulness: decompose answer into claims, verify each against context
- answer relevance: does the answer address the question (1-5)
- context precision: fraction of retrieved chunks relevant to the question
"""
import json
from app.config import settings
from app.core.llm import llm

def _j(system: str, user: str) -> dict | None:
    try:
        return json.loads(llm.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            json_mode=True, temperature=0.0, model=settings.judge_model).content)
    except (json.JSONDecodeError, TypeError, Exception):
        return None

def judge_faithfulness(question: str, answer: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {"score": None, "unsupported": []}
    context = "\n\n---\n\n".join(f"[{i+1}] {c['content']}" for i, c in enumerate(chunks))

    out = _j("You decompose answers into atomic factual claims. Respond with ONLY JSON: "
             '{"claims": ["..."]}. Empty list if there are no factual claims.',
             f"Question: {question}\n\nAnswer: {answer}") or {}
    claims = out.get("claims") or []
    if not claims:
        return {"score": None, "unsupported": []}

    out = _j("You verify claims against context. For each claim decide whether the context "
             'fully supports it. Respond with ONLY JSON: {"verdicts": [{"claim": "...", '
             '"supported": true, "reason": "..."}]}',
             f"Context:\n{context}\n\nClaims:\n" + "\n".join(f"- {c}" for c in claims)) or {}
    verdicts = out.get("verdicts") or []
    if not verdicts:
        return {"score": None, "unsupported": []}
    unsupported = [v["claim"] for v in verdicts if not v.get("supported")]
    return {"score": 1 - len(unsupported) / len(verdicts), "unsupported": unsupported}

def judge_relevance(question: str, answer: str) -> float | None:
    out = _j("Rate 1-5 how well the assistant's answer addresses the user's question. "
             "5 = fully addresses it, 1 = does not address it at all, 3 = partially. "
             'Respond with ONLY JSON: {"score": n, "reason": "..."}',
             f"Question: {question}\n\nAnswer: {answer}")
    score = (out or {}).get("score")
    return float(score) if isinstance(score, (int, float)) else None

def judge_context_precision(question: str, chunks: list[dict]) -> float | None:
    if not chunks:
        return None
    listed = "\n".join(f"[{i+1}] {c['content'][:800]}" for i, c in enumerate(chunks))
    out = _j("For each retrieved chunk, decide if it is useful for answering the question. "
             'Respond with ONLY JSON: {"chunks": [{"index": 1, "relevant": true}]}',
             f"Question: {question}\n\nChunks:\n{listed}")
    verdicts = (out or {}).get("chunks") or []
    if not verdicts:
        return None
    return sum(1 for v in verdicts if v.get("relevant")) / len(verdicts)
