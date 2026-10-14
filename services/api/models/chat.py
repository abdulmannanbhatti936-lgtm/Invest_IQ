import datetime
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class ChatMessage(Base):
    """
    One message of a user's chat with the assistant (PRD.md FR37-FR41). An assistant row records
    what it was grounded on (context version, hash and the ids of the rows it was built from),
    which provider and model wrote it, and the result of the figure check, so any reply can be
    re-checked later against exactly the data it was given.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
        CheckConstraint("language IN ('en', 'ur', 'ur-latn')", name="ck_chat_messages_language"),
        CheckConstraint(
            "figure_check IS NULL OR figure_check IN ('passed', 'regenerated', 'fallback')",
            name="ck_chat_messages_figure_check",
        ),
        Index("ix_chat_messages_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Assistant rows only
    context_version = Column(String, nullable=True)
    context_hash = Column(String(64), nullable=True)
    context_refs = Column(JSONB, nullable=True)
    prompt_version = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    figure_check = Column(String, nullable=True)
    figure_check_detail = Column(JSONB, nullable=True)
    sources = Column(JSONB, nullable=True)
