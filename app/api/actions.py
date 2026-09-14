from fastapi import APIRouter
from app.core import tools

router = APIRouter(prefix="/api/actions")

@router.post("/{action_id}/approve")
def approve(action_id: str, approver: str = "admin"):
    return tools.approve_action(action_id, approver)

@router.post("/{action_id}/reject")
def reject(action_id: str, rejected_by: str = "admin"):
    return tools.reject_action(action_id, rejected_by)