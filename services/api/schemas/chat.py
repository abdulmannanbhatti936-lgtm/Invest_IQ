"""Chat API shapes (PRD.md FR37-FR41)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from schemas.types import UTCDateTime

MAX_MESSAGE_CHARS = 1000


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # The language toggle; a message written in Roman Urdu is answered in Roman Urdu anyway
    language: Literal["en", "ur"]

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message is empty")
        return value


class SourceTag(BaseModel):
    """Where the figures in a reply came from, e.g. the portfolio generated on a date."""

    kind: Literal["portfolio", "prediction", "sentiment", "backtest", "price", "risk_profile"]
    ticker: str | None = None
    date: str | None = None


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    language: Literal["en", "ur", "ur-latn"]
    created_at: UTCDateTime
    sources: list[SourceTag] = []
    # passed / regenerated / fallback on assistant messages (Phases.md Phase 8 figure check)
    figure_check: str | None = None


class SendMessageResponse(BaseModel):
    user_message: ChatMessageOut
    reply: ChatMessageOut


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageOut]  # newest first
    next_before: uuid.UUID | None
    chat_available: bool
    unavailable_reason: Literal["not_configured"] | None = None
