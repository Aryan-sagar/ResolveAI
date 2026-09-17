import json
from app.core.llm import llm

ENRICH_SYSTEM = """You enrich freshly-created support tickets for a support ops team.
Given the ticket fields and the customer's original message, respond with ONLY valid JSON:
{"category": "...", "sentiment": "frustrated"|"neutral"|"positive",
 "summary": "one sentence", "suggested_next_action": "one concrete step for the agent",
 "priority_suggestion": "low"|"medium"|"high"}
Categories: damaged_item, wrong_item, late_delivery, billing, account_access, product_defect, other."""

def enrich_ticket(ticket_args: dict, customer_message: str) -> dict | None:
    try:
        return json.loads(llm.chat(
            [{"role": "system", "content": ENRICH_SYSTEM},
             {"role": "user", "content":
              f"Customer message: {customer_message}\n\nTicket fields: {json.dumps(ticket_args)}"}],
            json_mode=True, temperature=0.0).content)
    except Exception:
        return None  # enrichment is best-effort; never blocks ticket creation