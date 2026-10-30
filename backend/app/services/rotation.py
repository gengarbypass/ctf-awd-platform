from datetime import timedelta

from sqlalchemy import func, select

from ..audit import audit
from ..config import settings
from ..models import Flag, InjectStatus, Match, MatchStatus, Round, Service, Target, as_utc, utcnow
from ..security import generate_flag, hash_flag


async def rotate_match(db, match: Match, adapter, broker=None) -> Round | None:
    if match.status != MatchStatus.RUNNING:
        return None
    now = utcnow()
    latest = (await db.execute(
        select(Round).where(Round.match_id == match.id).order_by(Round.round_no.desc()).limit(1)
    )).scalar_one_or_none()
    if latest and now < as_utc(latest.ends_at):
        await expire_flags(db, now)
        return latest

    round_number = ((await db.execute(
        select(func.max(Round.round_no)).where(Round.match_id == match.id)
    )).scalar() or 0) + 1
    new_round = Round(
        match_id=match.id,
        round_no=round_number,
        starts_at=now,
        ends_at=now + timedelta(seconds=match.round_seconds),
        status="ACTIVE",
    )
    db.add(new_round)
    match.current_round = round_number
    await db.flush()
    if latest:
        latest.status = "CLOSED"
    targets = list((await db.execute(select(Target))).scalars())
    created: list[tuple[Flag, Target, Service, str]] = []
    for target in targets:
        service = await db.get(Service, target.service_id)
        plaintext = generate_flag(
            settings.flag_hmac_secret,
            match.id,
            new_round.id,
            target.team_id,
            service.id,
        )
        flag = Flag(
            round_id=new_round.id,
            target_id=target.id,
            flag_hash=hash_flag(plaintext),
            valid_from=now,
            valid_to=new_round.ends_at + timedelta(seconds=match.grace_seconds),
            inject_status=InjectStatus.PENDING,
        )
        db.add(flag)
        created.append((flag, target, service, plaintext))
    await db.commit()

    for flag, target, service, plaintext in created:
        try:
            await adapter.inject_flag(target, service, plaintext)
            flag.inject_status = InjectStatus.ACTIVE
        except Exception as exc:
            flag.inject_status = InjectStatus.FAILED
            await audit(db, None, "flag.injection_failed", "target", target.id, {"error": str(exc)[:500]})
            if broker:
                await broker.publish("target.status", {"target_id": target.id, "status": "FLAG_FAILED"})
        await db.commit()
    await expire_flags(db, utcnow())
    await audit(db, None, "flag.round_rotated", "round", new_round.id, {
        "match_id": match.id,
        "round_no": new_round.round_no,
        "target_count": len(created),
    })
    await db.commit()
    return new_round


async def expire_flags(db, now) -> None:
    flags = list((await db.execute(select(Flag).where(Flag.inject_status.in_([
        InjectStatus.ACTIVE,
        InjectStatus.FAILED,
    ])))).scalars())
    changed = False
    for flag in flags:
        if now > as_utc(flag.valid_to):
            flag.inject_status = InjectStatus.EXPIRED
            changed = True
    if changed:
        await db.commit()
