"""
One chat turn, end to end (Architecture.md §12, Workflow.md Step 8.3; PRD.md FR37-FR41):

1. per-user rate limit (10 messages per 5 minutes, 100 per day; fails open like the auth limiter);
2. the reply language: the toggle, or Roman Urdu if the user wrote in it;
3. the grounding context, rebuilt from the database for this message;
4. the last 6 messages as conversation memory, within the 12k-token budget;
5. the provider call (45 s deadline for everything below);
6. the figure check; one regeneration with the failed figures named; then a fixed fallback;
7. both messages stored together, only once a reply exists, so a failed send can be resent.

Message text and figures are never written to the logs (PRD.md §8.4): only ids, counts,
latency and the check result.
"""

import datetime
import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.config import settings
from core.redis import get_redis_client
from integrations.llm import Provider, Turn, get_provider
from models.chat import ChatMessage
from models.user import User
from services import chat_context, chat_figure_check, chat_prompt
from services.chat_language import reply_language

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 6
HISTORY_MESSAGE_CHARS = 1500
DEADLINE_S = 45.0
MAX_REPLY_TOKENS = 700
TEMPERATURE = 0.2


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__("chat rate limit")
        self.retry_after = retry_after


def _limit(key: str, limit: int, window: int) -> int | None:
    """Counts one message; returns the seconds to wait if the limit is now exceeded."""
    client = get_redis_client()
    count = client.incr(key)
    if count == 1:
        client.expire(key, window)
    if count > limit:
        ttl = client.ttl(key)
        return ttl if ttl and ttl > 0 else window
    return None


def check_rate_limit(user: User) -> None:
    day = datetime.datetime.now(chat_context.PKT).date().isoformat()
    try:
        wait = _limit(
            f"chat:rl:window:{user.id}",
            settings.CHAT_LIMIT_PER_WINDOW,
            settings.CHAT_LIMIT_WINDOW_SECONDS,
        ) or _limit(f"chat:rl:day:{user.id}:{day}", settings.CHAT_LIMIT_PER_DAY, 24 * 3600)
    except Exception as e:
        logger.warning("Chat rate limit SKIPPED (Redis unavailable: %s)", type(e).__name__)
        return
    if wait:
        raise RateLimited(wait)


def recent_messages(db: Session, user: User, limit: int = HISTORY_MESSAGES) -> list[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def _turns(history: list[ChatMessage], content: str, budget_chars: int) -> list[Turn]:
    """The memory turns plus the new message; the oldest turns go first if over budget."""
    turns = [Turn(m.role, m.content[:HISTORY_MESSAGE_CHARS]) for m in history]
    while turns and sum(len(t.content) for t in turns) + len(content) > budget_chars:
        turns.pop(0)
    # The providers expect the conversation to start with a user turn
    while turns and turns[0].role != "user":
        turns.pop(0)
    return [*turns, Turn("user", content)]


@dataclass
class Reply:
    text: str
    figure_check: str
    detail: dict
    sources: list[dict]
    model: str
    input_tokens: int | None
    output_tokens: int | None


def _add(a: int | None, b: int | None) -> int | None:
    return None if a is None and b is None else (a or 0) + (b or 0)


def generate_reply(
    context: chat_context.ChatContext,
    turns: list[Turn],
    language: str,
    user_message: str,
    provider: Provider | None = None,
) -> Reply:
    """`provider` defaults to the configured one; the evaluation passes each model it compares."""
    provider = provider or get_provider()
    deadline = time.monotonic() + DEADLINE_S
    failed: list[str] | None = None
    attempts, tokens_in, tokens_out = [], None, None
    for attempt in (1, 2):
        result = provider.complete(
            chat_prompt.system_prompt(context.json, language, failed),
            turns,
            max_tokens=MAX_REPLY_TOKENS,
            temperature=TEMPERATURE,
            deadline=deadline,
        )
        tokens_in, tokens_out = _add(tokens_in, result.input_tokens), _add(
            tokens_out, result.output_tokens
        )
        check = chat_figure_check.check_reply(result.text, context, user_message)
        attempts.append(check.detail())
        if check.passed:
            sources = [context.sources[s] for s in check.matched_sources if s in context.sources]
            return Reply(
                text=result.text,
                figure_check="passed" if attempt == 1 else "regenerated",
                detail={"attempts": attempts},
                sources=sources,
                model=result.model,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
            )
        failed = check.unmatched + check.number_words
        logger.warning(
            "Chat reply failed the figure check (attempt %d): %d unmatched, %d in words",
            attempt,
            len(check.unmatched),
            len(check.number_words),
        )
    return Reply(
        text=chat_prompt.FALLBACK[language],
        figure_check="fallback",
        detail={"attempts": attempts},
        sources=[],
        model=result.model,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
    )


def send_message(
    db: Session, user: User, content: str, toggle: str
) -> tuple[ChatMessage, ChatMessage]:
    """Raises RateLimited, or LLMError (and its subclasses) when no reply could be made."""
    check_rate_limit(user)
    started = time.monotonic()
    language = reply_language(content, toggle)
    history = recent_messages(db, user)
    context = chat_context.build_context(
        db,
        user,
        content,
        [m.content for m in history if m.role == "user"],
        language,
    )
    history_chars = sum(min(len(m.content), HISTORY_MESSAGE_CHARS) for m in history)
    context = chat_context.fit_to_budget(context, history_chars + len(content))
    budget_chars = (
        chat_context.MAX_INPUT_TOKENS - chat_context.estimate_tokens(context.json)
    ) * chat_context.CHARS_PER_TOKEN
    turns = _turns(history, content, budget_chars)

    reply = generate_reply(context, turns, language, content)
    latency_ms = int((time.monotonic() - started) * 1000)

    now = datetime.datetime.now(datetime.timezone.utc)
    user_row = ChatMessage(
        id=uuid.uuid4(), user_id=user.id, role="user", content=content, language=language,
        created_at=now,
    )  # fmt: skip
    reply_row = ChatMessage(
        id=uuid.uuid4(),
        user_id=user.id,
        role="assistant",
        content=reply.text,
        language=language,
        # A microsecond later, so the pair always sorts user-first
        created_at=now + datetime.timedelta(microseconds=1),
        context_version=context.version,
        context_hash=context.hash,
        context_refs={**context.refs, "trimmed": context.trimmed},
        prompt_version=chat_prompt.PROMPT_VERSION,
        provider=settings.LLM_PROVIDER,
        model=reply.model,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        latency_ms=latency_ms,
        figure_check=reply.figure_check,
        figure_check_detail=reply.detail,
        sources=reply.sources,
    )
    db.add_all([user_row, reply_row])
    db.commit()
    logger.info(
        "Chat reply %s: check=%s, latency=%d ms, tokens in/out=%s/%s",
        reply_row.id,
        reply.figure_check,
        latency_ms,
        reply.input_tokens,
        reply.output_tokens,
    )
    return user_row, reply_row


def history_page(
    db: Session, user: User, before: uuid.UUID | None, limit: int
) -> tuple[list[ChatMessage], uuid.UUID | None] | None:
    """Newest first. None if `before` is not one of this user's messages."""
    query = db.query(ChatMessage).filter(ChatMessage.user_id == user.id)
    if before is not None:
        anchor = query.filter(ChatMessage.id == before).first()
        if anchor is None:
            return None
        query = query.filter(
            (ChatMessage.created_at < anchor.created_at)
            | ((ChatMessage.created_at == anchor.created_at) & (ChatMessage.id < anchor.id))
        )
    rows = (
        query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit + 1).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (rows[-1].id if more else None)


def clear_history(db: Session, user: User) -> int:
    deleted = db.query(ChatMessage).filter(ChatMessage.user_id == user.id).delete()
    db.commit()
    return deleted
