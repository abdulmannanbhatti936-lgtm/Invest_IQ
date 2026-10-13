"""
One chat turn, end to end (Architecture.md §12, Workflow.md Step 8.3; PRD.md FR37-FR41):

1. per-user rate limit (10 messages per 5 minutes, 100 per day; fails open like the auth limiter);
2. the reply language: the toggle, or Roman Urdu if the user wrote in it;
3. the grounding context, rebuilt from the database for this message;
4. the last 6 messages as conversation memory, within the provider's budget (12k tokens,
   Groq about 4k);
5. the provider call (45 s deadline for everything below), failing over to the backup once
   on a 429, 5xx or timeout;
6. markdown stripped, then the figure check; a draft that fails it or was cut off at the
   token limit is regenerated once with the reason named; then a fixed fallback;
7. both messages stored together, only once a reply exists, so a failed send can be resent.

Message text and figures are never written to the logs (PRD.md §8.4): only ids, counts,
latency and the check result.
"""

import copy
import datetime
import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.config import settings
from core.redis import get_redis_client
from integrations.llm import LLMUnavailable, Provider, Turn, get_providers
from models.chat import ChatMessage
from models.user import User
from services import chat_context, chat_figure_check, chat_prompt
from services.chat_language import reply_language

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 6
HISTORY_MESSAGE_CHARS = 1500
DEADLINE_S = 45.0
# Urdu takes more tokens than English for the same text (the prompt still asks ~180 words)
MAX_REPLY_TOKENS = {"en": 700, "ur": 1200, "ur-latn": 1200}
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


def _turns(history: list, content: str, budget_chars: int) -> list[Turn]:
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
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    # The context as this provider received it (trimmed to its budget): stored and hashed
    context: chat_context.ChatContext


def _add(a: int | None, b: int | None) -> int | None:
    return None if a is None and b is None else (a or 0) + (b or 0)


def prepare(
    context: chat_context.ChatContext, history: list, content: str, provider_name: str
) -> tuple[chat_context.ChatContext, list[Turn]]:
    """
    The context and memory turns fitted to one provider's budget (12k tokens, Groq about 4k).
    The full context is copied, so a failover to a provider with a smaller budget starts again
    from everything the database gave.
    """
    budget = settings.chat_context_tokens(provider_name)
    history_chars = sum(min(len(m.content), HISTORY_MESSAGE_CHARS) for m in history)
    fitted = chat_context.fit_to_budget(
        copy.deepcopy(context), history_chars + len(content), budget
    )
    budget_chars = (
        budget - chat_context.estimate_tokens(fitted.json)
    ) * chat_context.CHARS_PER_TOKEN
    return fitted, _turns(history, content, budget_chars)


def generate_reply(
    context: chat_context.ChatContext,
    history: list,
    content: str,
    language: str,
    providers: list[Provider] | None = None,
) -> Reply:
    """
    Up to two drafts. A draft is rejected when a figure fails the check or when it stopped at
    the token limit (it may be cut off mid-sentence); the second draft is told why, and if it is
    rejected too the fixed fallback is sent, so a cut-off or unchecked reply is never shown.
    A 429, 5xx or timeout from the primary moves the message to the backup, once.
    `providers` defaults to the configured ones; the evaluation passes each model it compares.
    """
    chain = list(providers or get_providers())
    deadline = time.monotonic() + DEADLINE_S
    failed: list[str] | None = None
    too_long = False
    attempts: list[dict] = []
    failover: dict | None = None
    tokens_in = tokens_out = None
    provider, fitted, result = chain[0], context, None

    for attempt in (1, 2):
        try:
            while True:
                provider = chain[0]
                fitted, turns = prepare(context, history, content, provider.name)
                try:
                    result = provider.complete(
                        chat_prompt.system_prompt(fitted.json, language, failed, too_long),
                        turns,
                        max_tokens=MAX_REPLY_TOKENS[language],
                        temperature=TEMPERATURE,
                        deadline=deadline,
                        retry=len(chain) == 1,
                    )
                    break
                except LLMUnavailable as e:
                    if not (e.failover and len(chain) > 1):
                        raise
                    failover = {"from": f"{provider.name}:{provider.model}", "reason": e.reason}
                    logger.warning("Chat failed over from %s (%s)", provider.name, e.reason)
                    chain = chain[1:]
        except LLMUnavailable:
            if attempt == 1:
                raise
            # The first draft was rejected and no second one came: send the fallback
            attempts.append({"provider": f"{provider.name}:{provider.model}", "error": True})
            break
        tokens_in = _add(tokens_in, result.input_tokens)
        tokens_out = _add(tokens_out, result.output_tokens)
        text = chat_prompt.plain_text(result.text)
        check = chat_figure_check.check_reply(text, fitted, content)
        attempts.append(
            {
                "provider": f"{provider.name}:{result.model}",
                **check.detail(),
                "truncated": result.truncated,
            }
        )
        if check.passed and not result.truncated:
            sources = [fitted.sources[s] for s in check.matched_sources if s in fitted.sources]
            return Reply(
                text=text,
                figure_check="passed" if attempt == 1 else "regenerated",
                detail={"attempts": attempts, "failover": failover},
                sources=sources,
                provider=provider.name,
                model=result.model,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                context=fitted,
            )
        failed = (check.unmatched + check.number_words) or None
        too_long = result.truncated
        logger.warning(
            "Chat draft rejected (attempt %d): %d unmatched, %d in words, cut off: %s",
            attempt,
            len(check.unmatched),
            len(check.number_words),
            result.truncated,
        )
    return Reply(
        text=chat_prompt.FALLBACK[language],
        figure_check="fallback",
        detail={"attempts": attempts, "failover": failover},
        sources=[],
        provider=provider.name,
        model=result.model if result else provider.model,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        context=fitted,
    )


def send_message(
    db: Session, user: User, content: str, toggle: str
) -> tuple[ChatMessage, ChatMessage]:
    """Raises RateLimited, or LLMUnavailable (and its subclasses) when no reply could be made."""
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
    reply = generate_reply(context, history, content, language)
    latency_ms = int((time.monotonic() - started) * 1000)

    now = datetime.datetime.now(datetime.timezone.utc)
    user_row = ChatMessage(
        id=uuid.uuid4(), user_id=user.id, role="user", content=content, language=language,
        created_at=now,
    )  # fmt: skip
    sent = reply.context
    reply_row = ChatMessage(
        id=uuid.uuid4(),
        user_id=user.id,
        role="assistant",
        content=reply.text,
        language=language,
        # A microsecond later, so the pair always sorts user-first
        created_at=now + datetime.timedelta(microseconds=1),
        context_version=sent.version,
        context_hash=sent.hash,
        context_refs={**sent.refs, "trimmed": sent.trimmed},
        prompt_version=chat_prompt.PROMPT_VERSION,
        # The provider and model that actually answered, after any failover
        provider=reply.provider,
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
        "Chat reply %s: %s, check=%s, latency=%d ms, tokens in/out=%s/%s",
        reply_row.id,
        reply.provider,
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
