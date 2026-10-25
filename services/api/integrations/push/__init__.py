from integrations.push.base import PushChannel, PushMessage, PushResult
from integrations.push.fcm import FcmWebChannel

# platform -> channel; Phase 10 adds "expo"
CHANNELS: dict[str, PushChannel] = {"web": FcmWebChannel()}


def channel_for(platform: str) -> PushChannel | None:
    return CHANNELS.get(platform)


__all__ = ["CHANNELS", "PushChannel", "PushMessage", "PushResult", "channel_for"]
