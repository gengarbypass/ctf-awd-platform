from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import asyncio
import json

from ..database import get_db
from ..dependencies import get_current_user, require_player
from ..models import Announcement, AnnouncementStatus, Flag, Submission, Target, Team, TeamStatus, User
from ..responses import success
from ..serializers import announcement_dict, match_dict, submission_dict, target_dict, user_dict
from ..services.ranking import current_match, scoreboard_snapshot


router = APIRouter(tags=["platform"])


@router.get("/users/me")
async def users_me(user: User = Depends(get_current_user)):
    return success(user_dict(user))


@router.get("/match/current")
async def match_current(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    match = await current_match(db)
    return success(match_dict(match) if match else None)


@router.get("/announcements")
async def announcements(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(Announcement).where(
        Announcement.status == AnnouncementStatus.PUBLISHED
    ).order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc()))).scalars().all()
    return success([announcement_dict(item) for item in items])


@router.get("/targets/mine")
async def targets_mine(user: User = Depends(require_player), db: AsyncSession = Depends(get_db)):
    if not user.team_id:
        return success([])
    targets = (await db.execute(select(Target).options(selectinload(Target.service)).where(
        Target.team_id == user.team_id
    ))).scalars().all()
    return success([target_dict(target) for target in targets])


@router.get("/targets/opponents")
async def targets_opponents(user: User = Depends(require_player), db: AsyncSession = Depends(get_db)):
    """公开比赛入口：只暴露队伍、服务和公网端口，不暴露容器或管理网信息。"""
    if not user.team_id:
        return success([])
    targets = (await db.execute(
        select(Target)
        .options(selectinload(Target.team), selectinload(Target.service))
        .join(Team, Team.id == Target.team_id)
        .where(Target.team_id != user.team_id, Team.status == TeamStatus.ACTIVE)
    )).scalars().all()
    targets.sort(key=lambda item: (item.team.team_no, item.service.service_no))
    return success([
        {
            "id": target.id,
            "team_id": target.team_id,
            "team_no": target.team.team_no,
            "team_name": target.team.name,
            "service_id": target.service_id,
            "service_code": target.service.code,
            "service_name": target.service.name,
            "protocol": target.service.protocol,
            "public_port": target.public_port,
            "status": target.status.value,
            "last_checked_at": target.last_health_at.isoformat() if target.last_health_at else None,
        }
        for target in targets
    ])


@router.get("/submissions/mine")
async def submissions_mine(user: User = Depends(require_player), db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(Submission).options(
        selectinload(Submission.user),
        selectinload(Submission.attacker_team),
        selectinload(Submission.victim_team),
        selectinload(Submission.flag).selectinload(Flag.target).selectinload(Target.service),
    ).where(
        Submission.attacker_team_id == user.team_id
    ).order_by(Submission.submitted_at.desc()).limit(500))).scalars().all()
    return success([submission_dict(item) for item in items])


@router.get("/scoreboard")
async def scoreboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return success(await scoreboard_snapshot(db))


@router.get("/scoreboard/events")
async def scoreboard_events(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    snapshot = await scoreboard_snapshot(db)

    async def stream():
        yield f"event: scoreboard.snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
        subscription = request.app.state.events.subscribe()
        iterator = subscription.__aiter__()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(iterator.__anext__(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except StopAsyncIteration:
                    break
                yield f"event: {message['event']}\ndata: {json.dumps(message['data'], ensure_ascii=False)}\n\n"
        finally:
            await subscription.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })
