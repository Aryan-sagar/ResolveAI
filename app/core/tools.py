import json, uuid
from typing import Any, Literal, Optional
from pydantic import BaseModel
from app.db.session import SessionLocal
from app.db.models import ToolCallRecord

# ---- Mock backend services (swap each for an httpx call to a real API later) ----
def _seed_orders():
    return {
        "ORD123": {"order_id": "ORD123", "customer_id": "CUST99", "status": "delivered",
                   "delivered_on": "2026-02-08", "amount": 1200, "currency": "INR",
                   "courier": "Delhivery", "items": ["Wireless Headphones"]},
        "ORD456": {"order_id": "ORD456", "customer_id": "CUST77", "status": "shipped",
                   "expected_delivery": "2026-02-14", "amount": 3400, "currency": "INR",
                   "courier": "BlueDart", "items": ["Coffee Maker"]},
        "ORD789": {"order_id": "ORD789", "customer_id": "CUST99", "status": "processing",
                   "amount": 850, "currency": "INR", "courier": None, "items": ["Desk Lamp"]},
    }

ORDERS = _seed_orders()
CUSTOMERS = {
    "CUST99": {"customer_id": "CUST99", "name": "Priya Sharma", "tier": "gold", "open_tickets": 1},
    "CUST77": {"customer_id": "CUST77", "name": "Rahul Verma", "tier": "silver", "open_tickets": 0},
}
TICKETS, CRM_NOTES, CALLBACKS = {}, {}, []

def reset_mock_state():
    """Restore pristine mock data. Exists for eval determinism — a ticket created
    by row 12 must not change what row 13 sees. Real APIs wouldn't need this."""
    global ORDERS, TICKETS, CRM_NOTES, CALLBACKS, PENDING_ACTIONS
    ORDERS = _seed_orders()
    TICKETS, CRM_NOTES, CALLBACKS = {}, {}, []
    PENDING_ACTIONS = {}

# ---- Typed argument models: the LLM never executes anything, it only proposes ----
class CreateTicketArgs(BaseModel):
    customer_id: str
    subject: str
    description: str
    priority: Literal["low", "medium", "high"] = "medium"

class OrderStatusArgs(BaseModel):
    order_id: str

class CustomerArgs(BaseModel):
    customer_id: str

class CRMNoteArgs(BaseModel):
    customer_id: str
    note: str

class CallbackArgs(BaseModel):
    customer_id: str
    preferred_time: str

class RefundArgs(BaseModel):
    order_id: str
    amount: float
    reason: str

CANCELLABLE_STATUSES = {"pending", "processing"}

class CancelOrderArgs(BaseModel):
    order_id: str
    reason: str

# ---- Implementations ----
def _create_ticket(a: CreateTicketArgs):
    tid = f"TICKET-{500 + len(TICKETS) + 1}"
    TICKETS[tid] = a.model_dump()
    return {"ticket_id": tid, "status": "open", "priority": a.priority}

def _order_status(a: OrderStatusArgs):
    return ORDERS.get(a.order_id) or {"error": f"order {a.order_id} not found"}

def _customer(a: CustomerArgs):
    return CUSTOMERS.get(a.customer_id) or {"error": "customer not found"}

def _crm_note(a: CRMNoteArgs):
    CRM_NOTES.setdefault(a.customer_id, []).append(a.note)
    return {"ok": True, "notes_on_file": len(CRM_NOTES[a.customer_id])}

def _callback(a: CallbackArgs):
    CALLBACKS.append(a.model_dump())
    return {"ok": True, "scheduled_for": a.preferred_time}

def _issue_refund(a: RefundArgs):
    order = ORDERS.get(a.order_id)
    if not order:
        return {"error": "order not found"}
    return {"refund_id": f"REF-{uuid.uuid4().hex[:6].upper()}", "order_id": a.order_id,
            "amount": a.amount, "currency": order.get("currency", "INR"),
            "status": "submitted to payment gateway"}

def _cancel_order(a: CancelOrderArgs) -> dict[str, Any]:
    order = ORDERS[a.order_id]
    order["status"] = "cancelled"
    order["cancellation_reason"] = a.reason
    return {
        "order_id": a.order_id,
        "status": "cancelled",
        "refund_due": order["amount"],
        "currency": order["currency"],
        "note": "The refund for a cancelled order is initiated separately.",
    }

IMPLEMENTATIONS = {
    "get_order_status": _order_status,
    "get_customer_details": _customer,
    "create_support_ticket": _create_ticket,
    "update_crm_note": _crm_note,
    "request_callback": _callback,
    "issue_refund": _issue_refund,
    "cancel_order": _cancel_order,
}
ARG_MODELS = {
    "get_order_status": OrderStatusArgs, "get_customer_details": CustomerArgs,
    "create_support_ticket": CreateTicketArgs, "update_crm_note": CRMNoteArgs,
    "request_callback": CallbackArgs, "issue_refund": RefundArgs,
    "cancel_order": CancelOrderArgs,
}

# ---- Risk policy engine ----
RISK = {
    "get_order_status": "low", "get_customer_details": "low",
    "create_support_ticket": "medium", "update_crm_note": "medium", "request_callback": "medium",
    "issue_refund": "high",   # high risk => never auto-executed
    "cancel_order": "high",
}
ROLE_REQUIRED = {"update_crm_note": {"agent", "admin"}}  # role-based permission check

PENDING_ACTIONS: dict[str, dict] = {}  # prod: Redis with TTL

# ---- OpenAI function-calling schemas ----
TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "get_order_status",
        "description": "Get the status, delivery date, amount and items of an order.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "Order ID, e.g. ORD123"}},
                       "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "get_customer_details",
        "description": "Get customer profile: name, tier, open ticket count.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}},
                       "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "create_support_ticket",
        "description": "Create a support ticket for a customer issue.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "string"}, "subject": {"type": "string"},
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]}},
            "required": ["customer_id", "subject", "description", "priority"]}}},
    {"type": "function", "function": {"name": "update_crm_note",
        "description": "Append a note to the customer's CRM record. Requires agent or admin role.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}, "note": {"type": "string"}},
                       "required": ["customer_id", "note"]}}},
    {"type": "function", "function": {"name": "request_callback",
        "description": "Schedule a callback for the customer.",
        "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}, "preferred_time": {"type": "string"}},
                       "required": ["customer_id", "preferred_time"]}}},
    {"type": "function", "function": {"name": "issue_refund",
        "description": "Issue a refund for an order. HIGH RISK: always requires human approval before execution.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"},
                       "reason": {"type": "string"}},
                       "required": ["order_id", "amount", "reason"]}}},
    {"type": "function", "function": {"name": "cancel_order",
        "description": "Cancel an order. HIGH RISK: always requires human approval before execution.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}, "reason": {"type": "string"}},
                       "required": ["order_id", "reason"]}}},
]

# ---- Preflight: deterministic eligibility checks for high-risk tools ----
# The LLM proposes; this layer decides. Prompt compliance is probabilistic;
# business rules cannot be.
def _preflight_cancel(a: CancelOrderArgs):
    order = ORDERS.get(a.order_id)
    if not order:
        return False, f"Order {a.order_id} not found."
    if order["status"] not in CANCELLABLE_STATUSES:
        return False, (f"Order {a.order_id} cannot be cancelled: it is already "
                       f"{order['status']}. Only pending or processing orders can be cancelled.")
    return True, None

def _preflight_refund(a: RefundArgs):
    order = ORDERS.get(a.order_id)
    if not order:
        return False, f"Order {a.order_id} not found."
    if not (0 < a.amount <= order["amount"]):
        return False, (f"Invalid refund amount {a.amount}: the order total is "
                       f"{order['amount']} {order.get('currency', '')}.")
    return True, None

PREFLIGHTS = {"cancel_order": _preflight_cancel, "issue_refund": _preflight_refund}

def execute_tool(name: str, arguments: dict, user_role: str = "customer") -> dict:
    if name not in IMPLEMENTATIONS:
        return {"status": "error", "error": f"unknown tool: {name}"}
    try:                                    # 1. validate args against the pydantic model
        args = ARG_MODELS[name](**arguments)
    except Exception as e:
        return {"status": "error", "error": f"invalid arguments: {e}"}
    if name in ROLE_REQUIRED and user_role not in ROLE_REQUIRED[name]:   # 2. permission check
        return {"status": "denied", "error": f"role '{user_role}' may not call {name}"}

    risk = RISK.get(name, "high")           # 3. risk policy
    db = SessionLocal()
    rec = ToolCallRecord(tool_name=name, arguments=arguments, risk_level=risk, status="started")
    db.add(rec); db.commit()
    try:
        if risk == "high":
            pre = PREFLIGHTS.get(name)
            if pre:
                ok, reason = pre(args)
                if not ok:
                    rec.status, rec.response = "ineligible", {"reason": reason}
                    db.commit()
                    return {"status": "ineligible", "reason": reason}

            action_id = uuid.uuid4().hex[:8]
            PENDING_ACTIONS[action_id] = {
                "record_id": rec.id,
                "name": name,
                "arguments": arguments,
            }
            rec.status = "pending_approval"
            db.commit()
            return {
                "status": "pending_approval",
                "action_id": action_id,
                "message": "This action requires human approval before execution.",
            }
        else:
            # low/medium risk: no human approval needed, run it now
            pre = PREFLIGHTS.get(name)
            if pre:
                ok, reason = pre(args)
                if not ok:
                    rec.status, rec.response = "ineligible", {"reason": reason}
                    db.commit()
                    return {"status": "ineligible", "reason": reason}

            result = IMPLEMENTATIONS[name](args)
            rec.status, rec.response = "success", result
            db.commit()
            return {"status": "success", "result": result}

    except Exception as e:
        rec.status, rec.response = "error", {"error": str(e)}
        db.commit()
        return {"status": "error", "reason": str(e)}
    finally:
        db.close()

def approve_action(action_id: str, approved_by: str = "admin") -> dict:
    a = PENDING_ACTIONS.pop(action_id, None)
    if not a:
        return {"status": "error", "error": "unknown or already-processed action"}
    args = ARG_MODELS[a["name"]](**a["arguments"])
    pre = PREFLIGHTS.get(a["name"])
    if pre:
        ok, reason = pre(args)
        if not ok:  # state changed while parked — refuse rather than execute stale intent
            db = SessionLocal()
            rec = db.get(ToolCallRecord, a["record_id"])
            rec.status, rec.approved_by, rec.response = "rejected", approved_by, {"reason": reason}
            db.commit(); db.close()
            return {"status": "rejected", "reason": f"no longer eligible: {reason}"}
    result = IMPLEMENTATIONS[a["name"]](args)
    db = SessionLocal()
    rec = db.get(ToolCallRecord, a["record_id"])
    rec.status, rec.approved_by, rec.response = "success", approved_by, result
    db.commit(); db.close()
    return {"status": "success", "result": result}

def reject_action(action_id: str, rejected_by: str = "admin") -> dict:
    a = PENDING_ACTIONS.pop(action_id, None)
    if not a:
        return {"status": "error", "error": "unknown or already-processed action"}
    db = SessionLocal()
    rec = db.get(ToolCallRecord, a["record_id"])
    rec.status, rec.approved_by = "rejected", rejected_by
    db.commit(); db.close()
    return {"status": "rejected"}

# ---- Preflight: deterministic eligibility checks for high-risk tools ----
# The LLM proposes; this layer decides. Prompt compliance is probabilistic;
# business rules cannot be.
def _preflight_cancel(a: CancelOrderArgs):
    order = ORDERS.get(a.order_id)
    if not order:
        return False, f"Order {a.order_id} not found."
    if order["status"] not in CANCELLABLE_STATUSES:
        return False, (f"Order {a.order_id} cannot be cancelled: it is already "
                       f"{order['status']}. Only pending or processing orders can be cancelled.")
    return True, None

def _preflight_refund(a: RefundArgs):
    order = ORDERS.get(a.order_id)
    if not order:
        return False, f"Order {a.order_id} not found."
    if not (0 < a.amount <= order["amount"]):
        return False, (f"Invalid refund amount {a.amount}: the order total is "
                       f"{order['amount']} {order.get('currency', '')}.")
    return True, None

PREFLIGHTS = {"cancel_order": _preflight_cancel, "issue_refund": _preflight_refund}