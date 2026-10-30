import os
from datetime import timedelta
from pathlib import Path

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_awd.db"
os.environ["ALLOW_IN_MEMORY_REDIS"] = "true"
os.environ["ALLOW_MOCK_DOCKER"] = "true"
os.environ["SESSION_SECURE_COOKIE"] = "false"
os.environ["SESSION_SECRET"] = "test-session-secret-with-at-least-32-characters"
os.environ["FLAG_HMAC_SECRET"] = "test-flag-secret-with-at-least-32-characters"
os.environ["MOCK_TARGET_ROOT"] = str(Path(__file__).parent / "mock-targets")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager

from app.database import SessionLocal, engine
from app.models import (
    Base,
    Flag,
    InjectStatus,
    Match,
    MatchStatus,
    Role,
    Round,
    Service,
    Target,
    TargetStatus,
    Team,
    User,
    utcnow,
)
from app.security import hash_flag, hash_password


@pytest_asyncio.fixture
async def db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    from app.main import app

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as http_client:
            yield http_client, db


async def make_game(db, team_count=3):
    now = utcnow()
    match = Match(name="Test", status=MatchStatus.RUNNING, starts_at=now - timedelta(seconds=2), ends_at=now + timedelta(hours=4))
    db.add(match)
    await db.flush()
    round_ = Round(match_id=match.id, round_no=1, starts_at=now - timedelta(seconds=2), ends_at=now + timedelta(seconds=300))
    db.add(round_)
    await db.flush()
    teams, users = [], []
    for number in range(1, team_count + 1):
        team = Team(team_no=number, name=f"Team {number}", invite_code=f"INVITE-{number}", current_score=1000)
        db.add(team)
        await db.flush()
        user = User(username=f"player{number}", password_hash=hash_password("Player123!"), role=Role.PLAYER, team_id=team.id)
        db.add(user)
        teams.append(team)
        users.append(user)
    await db.flush()
    return match, round_, teams, users


async def add_flag(db, round_, team, plaintext="flag{test-valid}"):
    service = Service(code=f"svc-{team.team_no}", name="Service", service_no=team.team_no, protocol="TCP", internal_port=80, public_base_port=80, image="test:image")
    db.add(service)
    await db.flush()
    target = Target(
        team_id=team.id,
        service_id=service.id,
        container_name=f"target-{team.team_no}",
        attack_ip=f"127.0.0.{team.team_no}",
        public_port=20000 + team.team_no * 100,
        volume_name=f"volume-{team.team_no}",
        gateway_host=f"gateway-{team.team_no}",
        status=TargetStatus.RUNNING,
    )
    db.add(target)
    await db.flush()
    now = utcnow()
    flag = Flag(round_id=round_.id, target_id=target.id, flag_hash=hash_flag(plaintext), valid_from=now - timedelta(seconds=2), valid_to=now + timedelta(seconds=300), inject_status=InjectStatus.ACTIVE)
    db.add(flag)
    await db.commit()
    return flag, target, service
