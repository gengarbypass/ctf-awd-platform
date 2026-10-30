import hashlib
import hmac
import time

from .config import settings
from .events import InMemoryEventBroker, RedisEventBroker


class InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, tuple[str, float]] = {}

    def _key(self, token: str) -> str:
        return hmac.new(settings.session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()

    async def set(self, token: str, user_id: str) -> None:
        self._sessions[self._key(token)] = (user_id, time.monotonic() + settings.session_ttl_seconds)

    async def get(self, token: str) -> str | None:
        key = self._key(token)
        item = self._sessions.get(key)
        if not item:
            return None
        user_id, expires = item
        if expires < time.monotonic():
            self._sessions.pop(key, None)
            return None
        return user_id

    async def delete(self, token: str) -> None:
        self._sessions.pop(self._key(token), None)


class RedisSessionStore:
    def __init__(self, broker: RedisEventBroker):
        self.client = broker.client

    def _key(self, token: str) -> str:
        digest = hmac.new(settings.session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        return f"session:{digest}"

    async def set(self, token: str, user_id: str) -> None:
        await self.client.set(self._key(token), user_id, ex=settings.session_ttl_seconds)

    async def get(self, token: str) -> str | None:
        return await self.client.get(self._key(token))

    async def delete(self, token: str) -> None:
        await self.client.delete(self._key(token))


def create_session_store(broker):
    if isinstance(broker, InMemoryEventBroker):
        return InMemorySessionStore()
    if isinstance(broker, RedisEventBroker):
        return RedisSessionStore(broker)
    raise TypeError("unsupported event broker")
