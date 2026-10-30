from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from ..audit import audit
from ..database import get_db
from ..dependencies import get_current_user
from ..models import Role, Target, TargetStatus, User, utcnow
from ..responses import APIError, success
from ..serializers import target_dict


router = APIRouter(prefix="/targets", tags=["targets"])


@router.post("/{target_id}/restart")
async def restart_target(
    target_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target = (await db.execute(select(Target).options(selectinload(Target.service), selectinload(Target.team)).where(Target.id == target_id))).scalar_one_or_none()
    if not target:
        raise APIError(404, "NOT_FOUND", "target not found")
    if user.role == Role.PLAYER and target.team_id != user.team_id:
        await audit(db, user.id, "target.restart_denied", "target", target.id, {"owner_team_id": target.team_id}, request)
        await db.commit()
        raise APIError(403, "FORBIDDEN", "cannot restart another team's target")
    if target.status == TargetStatus.STOPPED:
        raise APIError(409, "TARGET_STOPPED", "target is stopped")
    target.status = TargetStatus.RESTARTING
    target.consecutive_successes = 0
    target.unhealthy_since = target.unhealthy_since or utcnow()
    await request.app.state.target_adapter.restart(target)
    await audit(db, user.id, "target.manual_restart", "target", target.id, {"volume_preserved": True}, request)
    await db.commit()
    await request.app.state.events.publish("target.status", {"target_id": target.id, "status": target.status.value})
    return success(target_dict(target), message="target restarted")
