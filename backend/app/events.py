import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from .config import settings


class InMemoryEventBroker:
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        message = {"event": event, "data": data}
        for queue in tuple(self._subscribers):
            queue.put_nowait(message)

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    async def close(self) -> None:
        return None


class RedisEventBroker:
    def __init__(self, client: redis.Redis):
        self.client = client
        self.channel = "awd.events"

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        await self.client.publish(self.channel, json.dumps({"event": event, "data": data}))

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(self.channel)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message and message.get("type") == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(self.channel)
            await pubsub.close()

    async def close(self) -> None:
        await self.client.aclose()


async def create_event_broker():
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
        return RedisEventBroker(client)
    except (RedisError, OSError) as exc:
        await client.aclose()
        if settings.environment != "production" and settings.allow_in_memory_redis:
            return InMemoryEventBroker()
        raise RuntimeError(f"Redis is required: {exc}") from exc
