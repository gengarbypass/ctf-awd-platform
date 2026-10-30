import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from .config import settings
from .database import SessionLocal, dispose_database
from .events import create_event_broker
from .models import Match, MatchStatus, as_utc, utcnow
from .services.health import check_all_targets
from .services.rotation import rotate_match
from .target_adapter import create_target_adapter
from sqlalchemy import select


from .logging_config import configure_logging
configure_logging()
logger = logging.getLogger("awd.worker")
_memory_locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def distributed_lock(client, name: str):
    if client is None:
        lock = _memory_locks.setdefault(name, asyncio.Lock())
        await lock.acquire()
        try:
            yield True
        finally:
            lock.release()
        return
    token = secrets.token_hex(16)
    acquired = await client.set(name, token, nx=True, ex=300)
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
        await client.eval(script, 1, name, token)


async def run_worker() -> None:
    broker = await create_event_broker()
    adapter = create_target_adapter()
    redis_client = None if broker.__class__.__name__ == "InMemoryEventBroker" else broker.client
    logger.info("worker started")
    try:
        while True:
            async with SessionLocal() as db:
                matches = list((await db.execute(select(Match).where(Match.status == MatchStatus.RUNNING))).scalars())
                for match in matches:
                    if utcnow() > as_utc(match.ends_at):
                        match.status = MatchStatus.FINISHED
                        await db.commit()
                        continue
                    async with distributed_lock(redis_client, f"flag-rotate:{match.id}") as acquired:
                        if acquired:
                            await rotate_match(db, match, adapter, broker)
            async with SessionLocal() as db:
                async with distributed_lock(redis_client, "health-check:all") as acquired:
                    if acquired:
                        await check_all_targets(db, adapter, broker)
            await asyncio.sleep(min(settings.health_interval_seconds, 30))
    finally:
        await broker.close()
        await dispose_database()


if __name__ == "__main__":
    asyncio.run(run_worker())
