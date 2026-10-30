#!/usr/bin/env python3
"""Explicit idempotent demo data seeder. Never run automatically at application startup."""
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select

from app.database import SessionLocal, dispose_database
from app.models import Match, MatchStatus, Role, Service, Target, TargetStatus, Team, User, utcnow
from app.security import hash_password
from app.target_adapter import create_target_adapter


async def seed() -> None:
    adapter = create_target_adapter()
    async with SessionLocal() as db:
        teams = []
        for number in range(1, 4):
            team = (await db.execute(select(Team).where(Team.team_no == number))).scalar_one_or_none()
            if not team:
                team = Team(team_no=number, name=f"Demo Team {number:02d}", invite_code=f"DEMO-TEAM-{number:02d}", current_score=1000)
                db.add(team)
                await db.flush()
            teams.append(team)

        if not await db.scalar(select(User.id).where(User.username == "admin")):
            db.add(User(username="admin", password_hash=hash_password("Admin123!"), role=Role.ADMIN))
        for team_index, team in enumerate(teams, 1):
            for member_no in range(1, 4):
                username = "player1" if team_index == 1 and member_no == 1 else f"player{team_index}_{member_no}"
                if not await db.scalar(select(User.id).where(User.username == username)):
                    db.add(User(username=username, password_hash=hash_password("Player123!"), role=Role.PLAYER, team_id=team.id))

        services = []
        for number, (code, name) in enumerate((("web", "Demo Web"), ("api", "Demo API"), ("db", "Demo Database")), 1):
            service = (await db.execute(select(Service).where(Service.code == code))).scalar_one_or_none()
            if not service:
                service = Service(
                    code=code,
                    name=name,
                    service_no=number,
                    protocol="HTTP",
                    internal_port=80,
                    public_base_port=80,
                    flag_path="/data/flag",
                    image="nginx:stable-alpine",
                    check_config={"path": "/", "status": 200},
                )
                db.add(service)
                await db.flush()
            services.append(service)

        match = (await db.execute(select(Match).order_by(Match.created_at.desc()).limit(1))).scalar_one_or_none()
        if not match:
            now = utcnow()
            match = Match(name="Demo AWD Match", status=MatchStatus.DRAFT, starts_at=now, ends_at=now + timedelta(hours=4), round_seconds=300, grace_seconds=30)
            db.add(match)
            await db.flush()
        await db.commit()

        all_healthy = True
        for team in teams:
            for service in services:
                target = (await db.execute(select(Target).where(Target.team_id == team.id, Target.service_id == service.id))).scalar_one_or_none()
                if not target:
                    target = Target(
                        team_id=team.id,
                        service_id=service.id,
                        container_name=f"target-t{team.team_no:02d}-s{service.service_no:02d}",
                        attack_ip=f"172.31.{team.team_no}.{service.service_no}",
                        public_port=20000 + team.team_no * 100 + service.service_no,
                        volume_name=f"awd-t{team.team_no:02d}-s{service.service_no:02d}-data",
                        gateway_host=f"gateway-t{team.team_no:02d}",
                    )
                    db.add(target)
                    await db.flush()
                    await adapter.initialize_target(target, service, team.team_no)
                if target.status in {TargetStatus.CREATED, TargetStatus.STOPPED}:
                    await adapter.start(target)
                health = await adapter.check_health(target, service)
                target.status = TargetStatus.RUNNING if health.ok else TargetStatus.UNHEALTHY
                all_healthy = all_healthy and health.ok
                await db.commit()
        if match.status == MatchStatus.DRAFT and all_healthy:
            match.status = MatchStatus.READY
            await db.commit()
        print("Seeded admin/Admin123!, player1/Player123!, 3 teams with 3 players each, 3 services and 9 targets.")
    await dispose_database()


if __name__ == "__main__":
    asyncio.run(seed())
