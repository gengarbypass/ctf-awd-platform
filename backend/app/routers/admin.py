import csv
import io
import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..audit import audit
from ..config import settings
from ..database import get_db
from ..dependencies import require_admin
from ..models import (
    Announcement,
    AuditLog,
    Flag,
    HealthCheck,
    LedgerReason,
    Match,
    MatchStatus,
    Role,
    Round,
    ScoreLedger,
    Service,
    Submission,
    Target,
    TargetStatus,
    Team,
    TeamStatus,
    User,
    UserStatus,
    as_utc,
    utcnow,
)
from ..responses import APIError, success
from ..schemas import (
    AnnouncementCreate,
    AnnouncementUpdate,
    FreezeRequest,
    MatchCreate,
    MatchUpdate,
    ScoreAdjustRequest,
    ServiceCreate,
    ServiceUpdate,
    TargetInitializeRequest,
    TeamCreate,
    TeamUpdate,
    UserCreate,
    UserUpdate,
)
from ..security import hash_password
from ..serializers import (
    announcement_dict,
    iso,
    match_dict,
    service_dict,
    submission_dict,
    target_dict,
    team_dict,
    user_dict,
)
from ..services.ranking import build_live_scoreboard, current_match


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


async def _actor(user: User = Depends(require_admin)) -> User:
    return user


@router.get("/overview")
async def admin_overview(db: AsyncSession = Depends(get_db)):
    match = await current_match(db)
    teams = list((await db.execute(select(Team))).scalars())
    targets = list((await db.execute(select(Target).options(selectinload(Target.service), selectinload(Target.team)))).scalars())
    latest = list((await db.execute(select(Submission).options(
        selectinload(Submission.user),
        selectinload(Submission.attacker_team),
        selectinload(Submission.victim_team),
        selectinload(Submission.flag).selectinload(Flag.target).selectinload(Target.service),
    ).order_by(Submission.submitted_at.desc()).limit(6))).scalars())
    return success({
        "match": match_dict(match) if match else None,
        "team_count": len(teams),
        "online_team_count": sum(team.status == TeamStatus.ACTIVE for team in teams),
        "player_count": await db.scalar(select(func.count(User.id)).where(User.role == Role.PLAYER, User.status == UserStatus.ACTIVE)) or 0,
        "healthy_target_count": sum(target.status == TargetStatus.RUNNING for target in targets),
        "target_count": len(targets),
        "abnormal_targets": [target_dict(target) for target in targets if target.status != TargetStatus.RUNNING],
        "latest_submissions": [submission_dict(item) for item in latest],
    })


@router.get("/teams")
async def list_teams(db: AsyncSession = Depends(get_db)):
    teams = (await db.execute(select(Team).options(selectinload(Team.users)).order_by(Team.team_no))).scalars().all()
    return success([team_dict(team) for team in teams])


@router.post("/teams")
async def create_team(payload: TeamCreate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    invite_code = payload.invite_code or f"TARC-{payload.team_no:02d}-{secrets.token_hex(3).upper()}"
    if await db.scalar(select(Team.id).where((Team.team_no == payload.team_no) | (Team.name == payload.name) | (Team.invite_code == invite_code))):
        raise APIError(409, "TEAM_EXISTS", "team number, name or invite code already exists")
    team = Team(**payload.model_dump(exclude_none=True), invite_code=invite_code, current_score=settings.initial_team_score)
    db.add(team)
    await db.flush()
    await audit(db, actor.id, "team.create", "team", team.id, payload.model_dump(), request)
    await db.commit()
    return success(team_dict(team), message="team created")


@router.put("/teams/{team_id}")
async def update_team(team_id: str, payload: TeamUpdate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, team_id)
    if not team:
        raise APIError(404, "NOT_FOUND", "team not found")
    changes = payload.model_dump(exclude_unset=True, exclude={"reset_score"})
    for key, value in changes.items():
        if key == "status":
            value = TeamStatus(value)
        setattr(team, key, value)
    if payload.reset_score:
        match = await current_match(db)
        if match and match.status not in {MatchStatus.DRAFT, MatchStatus.READY}:
            raise APIError(409, "MATCH_ACTIVE", "scores can only be reset before a match starts")
        team.current_score = settings.initial_team_score
        team.attack_count = 0
        team.breached_count = 0
        team.last_score_at = None
    await audit(db, actor.id, "team.update", "team", team.id, {"changes": changes, "reset_score": payload.reset_score}, request)
    await db.commit()
    return success(team_dict(team))


async def _check_team_capacity(db, team_id: str, exclude_user_id: str | None = None):
    team = await db.get(Team, team_id)
    if not team or team.status != TeamStatus.ACTIVE:
        raise APIError(400, "INVALID_TEAM", "team does not exist or is disabled")
    query = select(func.count(User.id)).where(User.team_id == team_id, User.role == Role.PLAYER, User.status == UserStatus.ACTIVE)
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    if (await db.scalar(query) or 0) >= 4:
        raise APIError(409, "TEAM_FULL", "team already has four players")
    return team


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(User).options(selectinload(User.team)).order_by(User.created_at))).scalars().all()
    return success([user_dict(user) for user in users])


@router.post("/users")
async def create_user(payload: UserCreate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(User.id).where(User.username == payload.username)):
        raise APIError(409, "USERNAME_EXISTS", "username already exists")
    if payload.role == Role.PLAYER and not payload.team_id:
        raise APIError(400, "TEAM_REQUIRED", "player must belong to a team")
    if payload.role == Role.PLAYER and payload.team_id:
        await _check_team_capacity(db, payload.team_id)
    if payload.role == Role.ADMIN and payload.team_id:
        raise APIError(400, "ADMIN_TEAM_NOT_ALLOWED", "administrator cannot belong to a team")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        team_id=payload.team_id if payload.role == Role.PLAYER else None,
    )
    db.add(user)
    await db.flush()
    await audit(db, actor.id, "user.create", "user", user.id, {"role": user.role.value, "team_id": user.team_id}, request)
    await db.commit()
    return success({"id": user.id, "username": user.username, "role": user.role.value, "team_id": user.team_id, "status": user.status.value})


@router.put("/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise APIError(404, "NOT_FOUND", "user not found")
    changes = payload.model_dump(exclude_unset=True)
    if payload.role:
        user.role = payload.role
        if user.role == Role.ADMIN:
            user.team_id = None
    if "team_id" in changes:
        if user.role == Role.ADMIN and changes["team_id"]:
            raise APIError(400, "ADMIN_TEAM_NOT_ALLOWED", "administrator cannot belong to a team")
        if changes["team_id"]:
            await _check_team_capacity(db, changes["team_id"], user.id)
        user.team_id = changes["team_id"]
    if user.role == Role.PLAYER and not user.team_id:
        raise APIError(400, "TEAM_REQUIRED", "player must belong to a team")
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.status:
        user.status = UserStatus(payload.status)
    await audit(db, actor.id, "user.update", "user", user.id, {"role": user.role.value, "team_id": user.team_id, "status": user.status.value, "password_reset": bool(payload.password)}, request)
    await db.commit()
    return success({"id": user.id, "username": user.username, "role": user.role.value, "team_id": user.team_id, "status": user.status.value})


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise APIError(404, "NOT_FOUND", "user not found")
    if user.id == actor.id:
        raise APIError(409, "SELF_DELETE_FORBIDDEN", "不能删除当前登录账号")
    if user.role != Role.PLAYER:
        raise APIError(409, "ADMIN_DELETE_FORBIDDEN", "只能删除选手账号")
    has_submission = await db.scalar(select(Submission.id).where(Submission.user_id == user.id).limit(1))
    if has_submission:
        raise APIError(409, "USER_HAS_SUBMISSIONS", "该选手已有提交记录，不能删除；请改为禁用账号")
    # 保留历史审计记录，但解除即将删除账号的外键引用。
    await db.execute(update(AuditLog).where(AuditLog.actor_id == user.id).values(actor_id=None))
    await audit(db, actor.id, "user.delete", "user", user.id, {"username": user.username, "team_id": user.team_id}, request)
    await db.delete(user)
    await db.commit()
    return success(message="user deleted")


@router.get("/matches")
async def list_matches(db: AsyncSession = Depends(get_db)):
    matches = (await db.execute(select(Match).order_by(Match.created_at.desc()))).scalars().all()
    return success([match_dict(match) for match in matches])


@router.post("/matches")
async def create_match(payload: MatchCreate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(Match.id).where(Match.status != MatchStatus.FINISHED))
    if existing:
        raise APIError(409, "ACTIVE_MATCH_EXISTS", "finish the current match before creating another")
    if payload.ends_at <= payload.starts_at:
        raise APIError(400, "INVALID_TIME_RANGE", "ends_at must be later than starts_at")
    match = Match(**payload.model_dump())
    db.add(match)
    await db.flush()
    await audit(db, actor.id, "match.create", "match", match.id, payload.model_dump(mode="json"), request)
    await db.commit()
    return success(match_dict(match))


@router.put("/matches/{match_id}")
async def update_match(match_id: str, payload: MatchUpdate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await db.get(Match, match_id)
    if not match:
        raise APIError(404, "NOT_FOUND", "match not found")
    if match.status != MatchStatus.DRAFT:
        raise APIError(409, "MATCH_NOT_EDITABLE", "only draft matches can be edited")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(match, key, value)
    if match.ends_at <= match.starts_at:
        raise APIError(400, "INVALID_TIME_RANGE", "ends_at must be later than starts_at")
    await audit(db, actor.id, "match.update", "match", match.id, payload.model_dump(exclude_unset=True, mode="json"), request)
    await db.commit()
    return success(match_dict(match))


async def _controllable_match(db) -> Match:
    match = await current_match(db)
    if not match:
        raise APIError(404, "MATCH_NOT_FOUND", "create a match first")
    return match


@router.put("/match")
async def update_current_match(payload: MatchUpdate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    return await update_match(match.id, payload, request, actor, db)


@router.post("/match/ready")
async def ready_match(request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    if match.status != MatchStatus.DRAFT:
        raise APIError(409, "INVALID_MATCH_STATE", "only a draft match can become ready")
    teams = list((await db.execute(select(Team).where(Team.status == TeamStatus.ACTIVE))).scalars())
    services = list((await db.execute(select(Service))).scalars())
    if not teams or not services:
        raise APIError(409, "CONFIGURATION_REQUIRED", "active teams and services are required")
    for team in teams:
        for service in services:
            target = (await db.execute(select(Target).where(Target.team_id == team.id, Target.service_id == service.id))).scalar_one_or_none()
            if not target or target.status != TargetStatus.RUNNING:
                raise APIError(409, "TARGET_NOT_HEALTHY", f"team {team.name} service {service.code} is not healthy")
    match.status = MatchStatus.READY
    await audit(db, actor.id, "match.ready", "match", match.id, request=request)
    await db.commit()
    return success(match_dict(match))


@router.post("/match/start")
async def start_match(request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    if match.status != MatchStatus.READY:
        raise APIError(409, "INVALID_MATCH_STATE", "only a ready match can start")
    teams = list((await db.execute(select(Team).where(Team.status == TeamStatus.ACTIVE))).scalars())
    if not teams:
        raise APIError(409, "TEAMS_REQUIRED", "at least one active team is required")
    for team in teams:
        members = await db.scalar(select(func.count(User.id)).where(User.team_id == team.id, User.role == Role.PLAYER, User.status == UserStatus.ACTIVE))
        if members not in {3, 4}:
            raise APIError(409, "INVALID_TEAM_SIZE", f"team {team.name} must have 3 or 4 active players")
    now = utcnow()
    duration = as_utc(match.ends_at) - as_utc(match.starts_at)
    if now < as_utc(match.starts_at):
        match.starts_at = now
        match.ends_at = now + duration
    if as_utc(match.ends_at) <= now:
        raise APIError(409, "MATCH_TIME_EXPIRED", "match end time is in the past")
    match.status = MatchStatus.RUNNING
    await audit(db, actor.id, "match.start", "match", match.id, request=request)
    await db.commit()
    return success(match_dict(match))


@router.post("/match/pause")
async def pause_match(request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    if match.status != MatchStatus.RUNNING:
        raise APIError(409, "INVALID_MATCH_STATE", "only a running match can pause")
    match.status = MatchStatus.PAUSED
    match.paused_at = utcnow()
    await audit(db, actor.id, "match.pause", "match", match.id, request=request)
    await db.commit()
    return success(match_dict(match))


@router.post("/match/resume")
async def resume_match(request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    if match.status != MatchStatus.PAUSED or not match.paused_at:
        raise APIError(409, "INVALID_MATCH_STATE", "only a paused match can resume")
    now = utcnow()
    paused_for = now - as_utc(match.paused_at)
    match.ends_at = as_utc(match.ends_at) + paused_for
    latest = (await db.execute(select(Round).where(Round.match_id == match.id, Round.status == "ACTIVE").order_by(Round.round_no.desc()).limit(1))).scalar_one_or_none()
    if latest:
        latest.ends_at = as_utc(latest.ends_at) + paused_for
        flags = (await db.execute(select(Flag).where(Flag.round_id == latest.id))).scalars().all()
        for flag in flags:
            flag.valid_to = as_utc(flag.valid_to) + paused_for
    match.status = MatchStatus.RUNNING
    match.paused_at = None
    await audit(db, actor.id, "match.resume", "match", match.id, {"paused_seconds": int(paused_for.total_seconds())}, request)
    await db.commit()
    return success(match_dict(match))


@router.post("/match/finish")
async def finish_match(request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    if match.status not in {MatchStatus.RUNNING, MatchStatus.PAUSED, MatchStatus.READY}:
        raise APIError(409, "INVALID_MATCH_STATE", "match cannot be finished from its current state")
    match.status = MatchStatus.FINISHED
    await audit(db, actor.id, "match.finish", "match", match.id, request=request)
    await db.commit()
    return success(match_dict(match))


@router.post("/match/freeze")
async def freeze_match(payload: FreezeRequest, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    match = await _controllable_match(db)
    if payload.frozen and not match.score_frozen:
        match.freeze_snapshot = await build_live_scoreboard(db, match)
        match.score_frozen = True
        match.frozen_at = utcnow()
    elif not payload.frozen:
        match.score_frozen = False
        match.freeze_snapshot = None
        match.frozen_at = None
    await audit(db, actor.id, "match.freeze" if payload.frozen else "match.unfreeze", "match", match.id, request=request)
    await db.commit()
    return success(match_dict(match))


@router.get("/services")
async def list_services(db: AsyncSession = Depends(get_db)):
    services = (await db.execute(select(Service).order_by(Service.service_no))).scalars().all()
    return success([service_dict(service) for service in services])


@router.post("/services")
async def create_service(payload: ServiceCreate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Service.id).where((Service.code == payload.code) | (Service.service_no == payload.service_no))):
        raise APIError(409, "SERVICE_EXISTS", "service code or number already exists")
    service = Service(**payload.model_dump())
    db.add(service)
    await db.flush()
    await audit(db, actor.id, "service.create", "service", service.id, payload.model_dump(), request)
    await db.commit()
    return success(service_dict(service))


@router.put("/services/{service_id}")
async def update_service(
    service_id: str,
    payload: ServiceUpdate,
    request: Request,
    actor: User = Depends(_actor),
    db: AsyncSession = Depends(get_db),
):
    service = await db.get(Service, service_id)
    if not service:
        raise APIError(404, "NOT_FOUND", "service not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(service, key, value)
    await audit(db, actor.id, "service.update", "service", service.id, changes, request)
    await db.commit()
    return success(service_dict(service))


@router.delete("/services/{service_id}")
async def delete_service(
    service_id: str,
    request: Request,
    force: bool = Query(False),
    actor: User = Depends(_actor),
    db: AsyncSession = Depends(get_db),
):
    service = await db.get(Service, service_id)
    if not service:
        raise APIError(404, "NOT_FOUND", "service not found")
    targets = list((await db.execute(select(Target).where(Target.service_id == service_id))).scalars())
    if targets and not force:
        raise APIError(
            409,
            "SERVICE_IN_USE",
            f"service has {len(targets)} target instance(s); delete targets first or retry with force",
        )
    for target in targets:
        try:
            await request.app.state.target_adapter.destroy(target)
        except Exception as exc:
            await audit(
                db,
                actor.id,
                "service.delete_cleanup_failed",
                "service",
                service_id,
                {"target_id": target.id, "error": str(exc)[:500]},
                request,
            )
            await db.commit()
            raise APIError(502, "TARGET_CLEANUP_FAILED", f"target cleanup failed: {str(exc)[:300]}") from exc
    if targets:
        target_ids = [target.id for target in targets]
        flag_ids = list((await db.execute(select(Flag.id).where(Flag.target_id.in_(target_ids)))).scalars())
        if flag_ids:
            # 保留历史提交记录，只解除已删除 Flag 的外键引用。
            await db.execute(update(Submission).where(Submission.flag_id.in_(flag_ids)).values(flag_id=None))
            await db.execute(delete(Flag).where(Flag.id.in_(flag_ids)))
        await db.execute(delete(HealthCheck).where(HealthCheck.target_id.in_(target_ids)))
        await db.execute(delete(Target).where(Target.id.in_(target_ids)))
    await db.delete(service)
    await audit(db, actor.id, "service.delete", "service", service_id, {"code": service.code, "target_count": len(targets)}, request)
    await db.commit()
    return success(message="service deleted")


@router.post("/services/{service_id}/pull-image")
async def pull_service_image(service_id: str, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    service = await db.get(Service, service_id)
    if not service:
        raise APIError(404, "NOT_FOUND", "service not found")
    try:
        await request.app.state.target_adapter.pull_image(service.image)
    except Exception as exc:
        await audit(db, actor.id, "service.image_pull_failed", "service", service.id, {"image": service.image, "error": str(exc)[:500]}, request)
        await db.commit()
        raise APIError(502, "IMAGE_PULL_FAILED", f"image pull failed: {str(exc)[:300]}") from exc
    await audit(db, actor.id, "service.image_pulled", "service", service.id, {"image": service.image}, request)
    await db.commit()
    return success({"image": service.image}, message="image ready")


@router.get("/targets")
async def list_targets(db: AsyncSession = Depends(get_db)):
    targets = (await db.execute(select(Target).options(selectinload(Target.service), selectinload(Target.team)).order_by(Target.public_port))).scalars().all()
    return success([target_dict(target, include_management=True) for target in targets])


@router.post("/targets")
async def initialize_targets(payload: TargetInitializeRequest, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    team_query = select(Team).where(Team.status == TeamStatus.ACTIVE)
    service_query = select(Service)
    if payload.team_ids is not None:
        team_query = team_query.where(Team.id.in_(payload.team_ids))
    if payload.service_ids is not None:
        service_query = service_query.where(Service.id.in_(payload.service_ids))
    teams = list((await db.execute(team_query)).scalars())
    services = list((await db.execute(service_query)).scalars())
    if not teams or not services:
        raise APIError(400, "INITIALIZATION_EMPTY", "no teams or services selected")
    actor_id = actor.id
    initialized, skipped = [], []
    for team in teams:
        for service in services:
            existing = await db.scalar(select(Target.id).where(Target.team_id == team.id, Target.service_id == service.id))
            if existing:
                skipped.append(existing)
                continue
            target = Target(
                team_id=team.id,
                service_id=service.id,
                container_name=f"target-t{team.team_no:02d}-s{service.service_no:02d}",
                attack_ip=f"172.31.{team.team_no}.{service.service_no}",
                public_port=20000 + team.team_no * 100 + service.service_no,
                volume_name=f"awd-t{team.team_no:02d}-s{service.service_no:02d}-data",
                gateway_host=f"gateway-t{team.team_no:02d}",
                gateway_port=settings.gateway_port,
            )
            db.add(target)
            await db.flush()
            target_id = target.id
            try:
                await request.app.state.target_adapter.initialize_target(target, service, team.team_no)
                if payload.start:
                    target.status = TargetStatus.STARTING
                    await request.app.state.target_adapter.start(target)
                    health = await request.app.state.target_adapter.check_health(target, service)
                    target.status = TargetStatus.RUNNING if health.ok else TargetStatus.UNHEALTHY
                    target.unhealthy_since = utcnow() if not health.ok else None
                await audit(db, actor_id, "target.initialize", "target", target_id, {"container": target.container_name, "volume": target.volume_name}, request)
                await db.commit()
                initialized.append(target_id)
            except Exception as exc:
                await db.rollback()
                await audit(db, actor_id, "target.initialize_failed", "target", target_id, {"error": str(exc)[:500]}, request)
                await db.commit()
                raise APIError(500, "TARGET_INITIALIZATION_FAILED", str(exc)[:300])
    return success({"initialized": initialized, "skipped": skipped}, message="target initialization complete")


async def _change_target_state(target_id: str, action: str, request: Request, actor: User, db: AsyncSession):
    target = (await db.execute(select(Target).options(selectinload(Target.service), selectinload(Target.team)).where(Target.id == target_id))).scalar_one_or_none()
    if not target:
        raise APIError(404, "NOT_FOUND", "target not found")
    if action == "start":
        await request.app.state.target_adapter.start(target)
        target.status = TargetStatus.STARTING
    else:
        await request.app.state.target_adapter.stop(target)
        target.status = TargetStatus.STOPPED
    await audit(db, actor.id, f"target.{action}", "target", target.id, {"volume_preserved": True}, request)
    await db.commit()
    await request.app.state.events.publish("target.status", {"target_id": target.id, "status": target.status.value})
    return success(target_dict(target), message=f"target {action} accepted")


@router.post("/targets/{target_id}/start")
async def start_target(target_id: str, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    return await _change_target_state(target_id, "start", request, actor, db)


@router.post("/targets/{target_id}/stop")
async def stop_target(target_id: str, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    return await _change_target_state(target_id, "stop", request, actor, db)


@router.get("/health")
async def health_records(target_id: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(HealthCheck)
    if target_id:
        query = query.where(HealthCheck.target_id == target_id)
    records = (await db.execute(query.order_by(HealthCheck.checked_at.desc()).limit(1000))).scalars().all()
    return success([{
        "id": item.id,
        "target_id": item.target_id,
        "status": item.status,
        "duration_ms": item.duration_ms,
        "error": item.error,
        "checked_at": iso(item.checked_at),
    } for item in records])


@router.get("/rounds")
async def list_rounds(db: AsyncSession = Depends(get_db)):
    rounds = (await db.execute(select(Round).order_by(Round.starts_at.desc()).limit(200))).scalars().all()
    return success([{"id": item.id, "match_id": item.match_id, "round_no": item.round_no, "starts_at": iso(item.starts_at), "ends_at": iso(item.ends_at), "status": item.status} for item in rounds])


@router.get("/submissions")
async def list_submissions(team_id: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Submission)
    if team_id:
        query = query.where(Submission.attacker_team_id == team_id)
    items = (await db.execute(query.options(
        selectinload(Submission.user),
        selectinload(Submission.attacker_team),
        selectinload(Submission.victim_team),
        selectinload(Submission.flag).selectinload(Flag.target).selectinload(Target.service),
    ).order_by(Submission.submitted_at.desc()).limit(1000))).scalars().all()
    return success([submission_dict(item) for item in items])


@router.get("/scores/ledger")
async def list_ledger(team_id: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(ScoreLedger)
    if team_id:
        query = query.where(ScoreLedger.team_id == team_id)
    items = (await db.execute(query.order_by(ScoreLedger.created_at.desc()).limit(5000))).scalars().all()
    teams = {team.id: team for team in (await db.execute(select(Team))).scalars()}
    return success([{
        "id": item.id,
        "team_id": item.team_id,
        "team_name": teams[item.team_id].name,
        "submission_id": item.submission_id,
        "delta": item.delta,
        "score_after": item.score_after,
        "reason": f"{item.reason.value}：{item.detail}" if item.detail else item.reason.value,
        "detail": item.detail,
        "created_at": iso(item.created_at),
    } for item in items])


@router.get("/announcements")
async def list_all_announcements(db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(Announcement).order_by(Announcement.published_at.desc()))).scalars().all()
    return success([announcement_dict(item) for item in items])


@router.post("/announcements")
async def publish_announcement(payload: AnnouncementCreate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    item = Announcement(**payload.model_dump())
    db.add(item)
    await db.flush()
    await audit(db, actor.id, "announcement.publish", "announcement", item.id, {"title": item.title, "level": item.level}, request)
    await db.commit()
    await request.app.state.events.publish("announcement.published", announcement_dict(item))
    return success(announcement_dict(item))


@router.put("/announcements/{announcement_id}")
async def update_announcement(announcement_id: str, payload: AnnouncementUpdate, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    item = await db.get(Announcement, announcement_id)
    if not item:
        raise APIError(404, "NOT_FOUND", "announcement not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await audit(db, actor.id, "announcement.update", "announcement", item.id, payload.model_dump(exclude_unset=True), request)
    await db.commit()
    return success(announcement_dict(item))


@router.post("/scores/adjust")
async def adjust_score(payload: ScoreAdjustRequest, request: Request, actor: User = Depends(_actor), db: AsyncSession = Depends(get_db)):
    team = (await db.execute(select(Team).where(Team.id == payload.team_id).with_for_update())).scalar_one_or_none()
    if not team:
        raise APIError(404, "NOT_FOUND", "team not found")
    before = team.current_score
    team.current_score += payload.delta
    if payload.delta > 0:
        team.last_score_at = utcnow()
    ledger = ScoreLedger(
        team_id=team.id,
        delta=payload.delta,
        score_after=team.current_score,
        reason=LedgerReason.MANUAL_ADJUST,
        detail=f"before={before}; after={team.current_score}; reason={payload.reason}",
    )
    db.add(ledger)
    await audit(db, actor.id, "score.manual_adjust", "team", team.id, {"before": before, "after": team.current_score, "delta": payload.delta, "reason": payload.reason}, request)
    await db.commit()
    await request.app.state.events.publish("score.changed", {"teams": [{"team_id": team.id, "score": team.current_score}], "manual": True})
    return success({
        "id": ledger.id,
        "team_id": team.id,
        "team_name": team.name,
        "submission_id": None,
        "delta": ledger.delta,
        "score_after": ledger.score_after,
        "reason": f"人工改分：{payload.reason}",
        "created_at": iso(ledger.created_at),
        "before": before,
    })


@router.get("/scores/export")
async def export_scores(db: AsyncSession = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["record_type", "team_no", "team_name", "team_id", "score_or_delta", "score_after", "attack_count", "breached_count", "reason", "submission_id", "created_at"])
    teams = (await db.execute(select(Team).order_by(Team.team_no))).scalars().all()
    for team in teams:
        writer.writerow(["TEAM", team.team_no, team.name, team.id, team.current_score, team.current_score, team.attack_count, team.breached_count, "", "", ""])
    ledgers = (await db.execute(select(ScoreLedger).order_by(ScoreLedger.created_at))).scalars().all()
    team_map = {team.id: team for team in teams}
    for item in ledgers:
        team = team_map[item.team_id]
        writer.writerow(["LEDGER", team.team_no, team.name, team.id, item.delta, item.score_after, "", "", item.reason.value, item.submission_id or "", iso(item.created_at)])
    content = "\ufeff" + output.getvalue()
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=awd-scores.csv"})


@router.get("/audit-logs")
async def audit_logs(
    action: str | None = None,
    object_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if object_type:
        query = query.where(AuditLog.object_type == object_type)
    items = (await db.execute(query.order_by(AuditLog.created_at.desc()).limit(limit))).scalars().all()
    actors = {user.id: user.username for user in (await db.execute(select(User))).scalars()}
    return success([{
        "id": item.id,
        "actor_id": item.actor_id,
        "actor_name": actors.get(item.actor_id, "worker" if item.actor_id is None else "未知用户"),
        "action": item.action,
        "object_type": item.object_type,
        "object_id": item.object_id,
        "detail": json.dumps(item.detail, ensure_ascii=False),
        "source_ip": item.source_ip,
        "request_id": item.request_id,
        "created_at": iso(item.created_at),
    } for item in items])
