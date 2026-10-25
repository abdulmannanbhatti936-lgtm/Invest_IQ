"""
What every push channel shares (Phase 7). A channel delivers one message to one device token
and says whether it arrived, or whether the token is dead and should be dropped. The dispatcher
(services/notification_dispatch.py) picks the channel by the device's platform, so Expo push
(Phase 10) is one more entry in `CHANNELS`, with no change to the agent or the dispatcher.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    # Path inside the app the tap opens (Design.md §19: never only the home screen)
    link: str
    # One OS notification per InvestIQ notification, even if it is delivered twice
    tag: str
    data: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PushResult:
    delivered: bool
    # The push service no longer knows this token (browser unsubscribed, app removed)
    token_invalid: bool = False
    detail: str = ""


class PushChannel(Protocol):
    platform: str

    def unavailable_reason(self) -> str | None:
        """Why this channel cannot send with the current configuration, or None."""

    def send(self, token: str, message: PushMessage) -> PushResult: ...
