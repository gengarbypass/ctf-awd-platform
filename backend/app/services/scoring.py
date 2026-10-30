import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    AuditLog,
    Flag,
    InjectStatus,
    LedgerReason,
    MatchStatus,
    Round,
    ScoreLedger,
    Submission,
    SubmissionResult,
    Target,
    Team,
    User,
    as_utc,
    utcnow,
)
from ..security import hash_flag
from ..responses import APIError
from .ranking import current_match


logger = logging.getLogger(__name__)
_sqlite_score_lock = asyncio.Lock()


def _submission_audit(item: Submission, flag_hash: str) -> AuditLog:
    return AuditLog(
        actor_id=item.user_id,
        action="flag.submit",
        object_type="submission",
        object_id=item.id,
        detail={"flag_hash": flag_hash, "result": item.result.value, "victim_team_id": item.victim_team_id},
        request_id=item.request_id,
    )


def _result(item: Submission, attacker_score: int | None = None) -> dict:
    data = {
        "submission_id": item.id,
        "result": item.result.value,
        "attacker_delta": item.attacker_delta,
        "victim_delta": item.victim_delta,
    }
    if attacker_score is not None:
        data["attacker_score"] = attacker_score
    return data


async def submit_flag(
    db: AsyncSession,
    user: User,
    flag_text: str,
    request_id: str,
    broker=None,
    now: datetime | None = None,
) -> dict:
    if db.bind and db.bind.dialect.name == "sqlite":
        async with _sqlite_score_lock:
            return await _submit_flag(db, user, flag_text, request_id, broker, now)
    return await _submit_flag(db, user, flag_text, request_id, broker, now)


async def _submit_flag(db, user, flag_text, request_id, broker, now) -> dict:
    now = now or utcnow()
    try:
        existing_request = (await db.execute(
            select(Submission).where(Submission.user_id == user.id, Submission.request_id == request_id)
        )).scalar_one_or_none()
        if existing_request:
            team = await db.get(Team, user.team_id)
            return _result(existing_request, team.current_score if team else None)

        if not user.team_id:
            raise ValueError("player must belong to a team")
        redis_client = getattr(broker, "client", None)
        if redis_client is not None:
            rate_key = f"flag-submit-rate:{user.id}:{int(now.timestamp())}"
            attempts = await redis_client.incr(rate_key)
            if attempts == 1:
                await redis_client.expire(rate_key, 2)
            if attempts > settings.flag_submit_rate_per_second:
                raise APIError(429, "RATE_LIMITED", "too many flag submissions, retry in one second")
        flag_hash = hash_flag(flag_text)
        match = await current_match(db)
        if not match or match.status != MatchStatus.RUNNING or now > as_utc(match.ends_at):
            if match and match.status == MatchStatus.RUNNING and now > as_utc(match.ends_at):
                match.status = MatchStatus.FINISHED
            item = Submission(
                request_id=request_id,
                user_id=user.id,
                attacker_team_id=user.team_id,
                result=SubmissionResult.MATCH_NOT_RUNNING,
            )
            db.add(item)
            await db.flush()
            db.add(_submission_audit(item, flag_hash))
            await db.commit()
            return _result(item)

        flag = (await db.execute(
            select(Flag).join(Round, Flag.round_id == Round.id).where(
                Flag.flag_hash == flag_hash,
                Round.match_id == match.id,
            )
        )).scalar_one_or_none()
        if not flag:
            item = Submission(
                request_id=request_id,
                user_id=user.id,
                attacker_team_id=user.team_id,
                result=SubmissionResult.INVALID,
            )
            db.add(item)
            await db.flush()
            db.add(_submission_audit(item, flag_hash))
            await db.commit()
            return _result(item)

        if now < as_utc(flag.valid_from) or now > as_utc(flag.valid_to) or flag.inject_status != InjectStatus.ACTIVE:
            if now > as_utc(flag.valid_to):
                flag.inject_status = InjectStatus.EXPIRED
            item = Submission(
                request_id=request_id,
                user_id=user.id,
                attacker_team_id=user.team_id,
                flag_id=flag.id,
                result=SubmissionResult.EXPIRED,
            )
            db.add(item)
            await db.flush()
            db.add(_submission_audit(item, flag_hash))
            await db.commit()
            return _result(item)

        target = await db.get(Target, flag.target_id)
        victim_team_id = target.team_id if target else None
        if not victim_team_id:
            raise RuntimeError("flag target has no owning team")
        if victim_team_id == user.team_id:
            item = Submission(
                request_id=request_id,
                user_id=user.id,
                attacker_team_id=user.team_id,
                victim_team_id=victim_team_id,
                flag_id=flag.id,
                result=SubmissionResult.OWN_TEAM,
            )
            db.add(item)
            await db.flush()
            db.add(_submission_audit(item, flag_hash))
            await db.commit()
            return _result(item)

        duplicate = (await db.execute(select(Submission).where(
            Submission.flag_id == flag.id,
            Submission.attacker_team_id == user.team_id,
            Submission.result == SubmissionResult.ACCEPTED,
        ))).scalar_one_or_none()
        if duplicate:
            item = Submission(
                request_id=request_id,
                user_id=user.id,
                attacker_team_id=user.team_id,
                victim_team_id=victim_team_id,
                flag_id=flag.id,
                result=SubmissionResult.DUPLICATE,
            )
            db.add(item)
            await db.flush()
            db.add(_submission_audit(item, flag_hash))
            await db.commit()
            return _result(item)

        item = Submission(
            request_id=request_id,
            user_id=user.id,
            attacker_team_id=user.team_id,
            victim_team_id=victim_team_id,
            flag_id=flag.id,
            result=SubmissionResult.ACCEPTED,
            attacker_delta=settings.attack_reward,
            victim_delta=-settings.victim_penalty,
            submitted_at=now,
        )
        db.add(item)
        try:
            await db.flush()
            db.add(_submission_audit(item, flag_hash))
        except IntegrityError:
            await db.rollback()
            existing = (await db.execute(select(Submission).where(
                Submission.user_id == user.id, Submission.request_id == request_id
            ))).scalar_one_or_none()
            if existing:
                return _result(existing)
            return await _record_concurrent_duplicate(db, user, flag.id, victim_team_id, request_id, flag_hash)

        team_ids = sorted((user.team_id, victim_team_id))
        locked_teams = (await db.execute(
            select(Team).where(Team.id.in_(team_ids)).order_by(Team.id).with_for_update()
        )).scalars().all()
        teams = {team.id: team for team in locked_teams}
        attacker = teams[user.team_id]
        victim = teams[victim_team_id]
        attacker.current_score += settings.attack_reward
        attacker.attack_count += 1
        attacker.last_score_at = now
        victim.current_score -= settings.victim_penalty
        victim.breached_count += 1
        db.add_all([
            ScoreLedger(
                team_id=attacker.id,
                submission_id=item.id,
                delta=settings.attack_reward,
                score_after=attacker.current_score,
                reason=LedgerReason.ATTACK,
                created_at=now,
            ),
            ScoreLedger(
                team_id=victim.id,
                submission_id=item.id,
                delta=-settings.victim_penalty,
                score_after=victim.current_score,
                reason=LedgerReason.BREACH,
                created_at=now,
            ),
        ])
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(
            select(Submission).where(Submission.user_id == user.id, Submission.request_id == request_id)
        )).scalar_one_or_none()
        if existing:
            return _result(existing)
        if "flag" not in locals() or "victim_team_id" not in locals():
            raise
        return await _record_concurrent_duplicate(db, user, flag.id, victim_team_id, request_id, flag_hash)
    except Exception:
        await db.rollback()
        raise

    if broker:
        try:
            await broker.publish("score.changed", {
                "match_id": match.id,
                "submission_id": item.id,
                "teams": [
                    {"team_id": attacker.id, "score": attacker.current_score},
                    {"team_id": victim.id, "score": victim.current_score},
                ],
            })
        except Exception as exc:
            logger.error("failed to publish committed score event: %s", exc)
    return _result(item, attacker.current_score)


async def _record_concurrent_duplicate(db, user, flag_id, victim_team_id, request_id, flag_hash) -> dict:
    item = Submission(
        request_id=request_id,
        user_id=user.id,
        attacker_team_id=user.team_id,
        victim_team_id=victim_team_id,
        flag_id=flag_id,
        result=SubmissionResult.DUPLICATE,
    )
    db.add(item)
    await db.flush()
    db.add(_submission_audit(item, flag_hash))
    await db.commit()
    return _result(item)
