"""
Web push through Firebase Cloud Messaging, HTTP v1 API (Architecture.md §3, Phase 7). The
service account file is read only through FIREBASE_SERVICE_ACCOUNT_FILE (outside the repo);
google-auth turns it into a short-lived OAuth token. Messages are data-only, so the app's
service worker (apps/web/public/push-sw.js) shows them with the same text in both languages.
A failure never raises: the caller records it and the in-app note stays.
"""

import logging
import threading

import httpx

from core.config import settings
from integrations.push.base import PushMessage, PushResult

logger = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
CONNECT_TIMEOUT_S = 3.0
READ_TIMEOUT_S = 5.0
# A push older than a day is no longer timely; FCM drops it instead of delivering it late
TTL_SECONDS = 86_400
TOKEN_GONE_CODES = {"UNREGISTERED"}


class FcmWebChannel:
    platform = "web"

    def __init__(self) -> None:
        self._credentials = None
        self._lock = threading.Lock()

    def unavailable_reason(self) -> str | None:
        return settings.push_unavailable_reason()

    def _access(self) -> tuple[str, str]:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        with self._lock:
            if self._credentials is None:
                self._credentials = service_account.Credentials.from_service_account_file(
                    settings.FIREBASE_SERVICE_ACCOUNT_FILE, scopes=[SCOPE]
                )
            if not self._credentials.valid:
                self._credentials.refresh(Request())
            return self._credentials.token, self._credentials.project_id

    def send(self, token: str, message: PushMessage) -> PushResult:
        try:
            access_token, project = self._access()
        except Exception as e:
            # Never log the file path or the key; the exception type is enough to act on
            logger.error("FCM sign-in failed: %s", type(e).__name__)
            return PushResult(False, detail=f"auth_failed:{type(e).__name__}")

        body = {
            "message": {
                "token": token,
                "data": {
                    **message.data,
                    "title": message.title,
                    "body": message.body,
                    "link": message.link,
                    "tag": message.tag,
                },
                "webpush": {"headers": {"Urgency": "high", "TTL": str(TTL_SECONDS)}},
            }
        }
        try:
            response = httpx.post(
                SEND_URL.format(project=project),
                json=body,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=httpx.Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
            )
        except httpx.HTTPError as e:
            return PushResult(False, detail=f"network:{type(e).__name__}")
        if response.status_code == 200:
            return PushResult(True)
        return PushResult(
            False,
            token_invalid=response.status_code == 404 or _error_code(response) in TOKEN_GONE_CODES,
            detail=f"http_{response.status_code}:{_error_code(response) or 'unknown'}",
        )


def _error_code(response: httpx.Response) -> str | None:
    try:
        details = response.json()["error"].get("details", [])
    except (ValueError, KeyError, AttributeError):
        return None
    for detail in details:
        if isinstance(detail, dict) and detail.get("errorCode"):
            return detail["errorCode"]
    return None
