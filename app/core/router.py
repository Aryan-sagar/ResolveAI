import json
from app.core.llm import llm

ROUTER_SYSTEM = """You classify customer support queries for routing. Respond with ONLY valid JSON:
{"intent": str, "requires_rag": bool, "requires_api": bool, "risk_level": "low"|"medium"|"high", "entities": {}}
Intents: policy_question, order_status, refund_request, complaint, ticket_request, callback_request, account_question, out_of_scope, unsafe.
requires_rag=true when the answer depends on policies, FAQs or documentation.
requires_api=true when live data or an action is needed (orders, tickets, CRM, refunds, callbacks)."""

def classify(query: str) -> dict:
    msg = llm.chat(
        [{"role": "system", "content": ROUTER_SYSTEM}, {"role": "user", "content": f"Query: {query}"}],
        json_mode=True, temperature=0.0,
    )
    try:
        return json.loads(msg.content)
    except (json.JSONDecodeError, TypeError):
        return {"intent": "unknown", "requires_rag": True, "requires_api": True,
                "risk_level": "medium", "entities": {}}