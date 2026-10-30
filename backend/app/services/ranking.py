from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Match, Target, TargetStatus, Team, TeamStatus, as_utc, utcnow
from ..serializers import iso


async def current_match(db: AsyncSession) -> Match | None:
    result = await db.execute(select(Match).order_by(Match.created_at.desc()).limit(1))
    return result.scalar_one_or_none()


def unhealthy_seconds(team_id: str, targets: list[Target], now: datetime) -> int:
    total = 0
    for target in targets:
        if target.team_id != team_id:
            continue
        total += target.total_unhealthy_seconds
        if target.unhealthy_since and target.status in {
            TargetStatus.UNHEALTHY,
            TargetStatus.RESTARTING,
            TargetStatus.MANUAL_INTERVENTION,
        }:
            total += max(0, int((now - as_utc(target.unhealthy_since)).total_seconds()))
    return total


async def build_live_scoreboard(db: AsyncSession, match: Match | None = None) -> dict:
    match = match or await current_match(db)
    now = utcnow()
    teams = list((await db.execute(select(Team).options(selectinload(Team.users)).where(Team.status == TeamStatus.ACTIVE))).scalars())
    targets = list((await db.execute(select(Target).options(selectinload(Target.service)))).scalars())
    rows = []
    for team in teams:
        team_targets = sorted((target for target in targets if target.team_id == team.id), key=lambda item: item.public_port)
        rows.append({
            "id": team.id,
            "team_no": team.team_no,
            "name": team.name,
            "invite_code": team.invite_code,
            "current_score": team.current_score,
            "attack_count": team.attack_count,
            "breached_count": team.breached_count,
            "member_count": len(team.__dict__.get("users") or []),
            "status": team.status.value,
            "unhealthy_seconds": unhealthy_seconds(team.id, targets, now),
            "last_scored_at": iso(team.last_score_at),
            "services": [{
                "service_code": target.service.code if target.service else None,
                "service_name": target.service.name if target.service else None,
                "status": target.status.value,
            } for target in team_targets],
        })

    def sort_key(row):
        last_score = row["last_scored_at"]
        last_score_dt = datetime.fromisoformat(last_score) if last_score else datetime.max.replace(tzinfo=timezone.utc)
        return (-row["current_score"], -row["attack_count"], row["unhealthy_seconds"], last_score_dt, row["team_no"])

    rows.sort(key=sort_key)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    legacy_rows = [{
        "team_id": row["id"],
        "team_no": row["team_no"],
        "team_name": row["name"],
        "score": row["current_score"],
        "attack_count": row["attack_count"],
        "breached_count": row["breached_count"],
        "unhealthy_seconds": row["unhealthy_seconds"],
        "last_score_at": row["last_scored_at"],
        "rank": row["rank"],
        "services": {
            "total": len(row["services"]),
            "running": sum(service["status"] == TargetStatus.RUNNING.value for service in row["services"]),
            "unhealthy": sum(service["status"] in {TargetStatus.UNHEALTHY.value, TargetStatus.MANUAL_INTERVENTION.value} for service in row["services"]),
            "recovering": sum(service["status"] in {TargetStatus.STARTING.value, TargetStatus.RESTARTING.value} for service in row["services"]),
        },
    } for row in rows]
    return {
        "match_id": match.id if match else None,
        "version": int(now.timestamp() * 1000),
        "frozen": False,
        "generated_at": iso(now),
        "teams": legacy_rows,
        "rows": rows,
    }


async def scoreboard_snapshot(db: AsyncSession) -> dict:
    match = await current_match(db)
    if match and match.score_frozen and match.freeze_snapshot:
        snapshot = dict(match.freeze_snapshot)
        snapshot["frozen"] = True
        return snapshot
    return await build_live_scoreboard(db, match)
