import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user, require_risk_profile
from integrations.llm import LLMBusy, LLMError
from models.chat import ChatMessage
from models.risk_profile import RiskProfile
from models.user import User
from schemas.chat import ChatHistoryResponse, SendMessageRequest, SendMessageResponse
from services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

ERRORS = {
    404: {"description": "detail.code: 'message_not_found' (an unknown `before` cursor)"},
    409: {"description": "detail.code: 'risk_profile_required'"},
    429: {"description": "detail.code: 'rate_limited'; Retry-After header in seconds"},
    503: {
        "description": (
            "detail.code: 'chat_unavailable'; detail.reason: 'not_configured', "
            "'provider_error' or 'provider_busy'"
        )
    },
}


def _message(row: ChatMessage) -> dict:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "language": row.language,
        "created_at": row.created_at,
        "sources": row.sources or [],
        "figure_check": row.figure_check,
    }


@router.post("/message", response_model=SendMessageResponse, status_code=201, responses=ERRORS)
def send_message(
    body: SendMessageRequest,
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Answers one message from the user's own data (FR39): the reply is grounded in a context
    rebuilt from the database for this message and every figure in it is checked against that
    context. Nothing is stored unless a reply was produced, so a failed send can be resent.
    """
    try:
        user_row, reply_row = chat_service.send_message(db, user, body.content, body.language)
    except chat_service.RateLimited as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many messages.",
                "retry_after": exc.retry_after,
            },
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except LLMError as exc:
        headers = (
            {"Retry-After": str(int(exc.retry_after))}
            if isinstance(exc, LLMBusy) and exc.retry_after
            else None
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "chat_unavailable",
                "reason": exc.reason,
                "message": "The assistant is not available right now.",
            },
            headers=headers,
        ) from exc
    return {"user_message": _message(user_row), "reply": _message(reply_row)}


@router.get("/history", response_model=ChatHistoryResponse, responses=ERRORS)
def history(
    before: uuid.UUID | None = None,
    limit: int = Query(default=30, ge=1, le=50),
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The user's own messages, newest first; `before` pages to older ones."""
    page = chat_service.history_page(db, user, before, limit)
    if page is None:
        raise HTTPException(
            status_code=404, detail={"code": "message_not_found", "message": "Message not found."}
        )
    rows, next_before = page
    reason = settings.chat_unavailable_reason()
    return {
        "messages": [_message(r) for r in rows],
        "next_before": next_before,
        "chat_available": reason is None,
        "unavailable_reason": "not_configured" if reason else None,
    }


@router.delete("/history", status_code=204, responses=ERRORS)
def clear_history(
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes every message of this user's chat; nobody else's is touched."""
    chat_service.clear_history(db, user)
    return Response(status_code=204)
