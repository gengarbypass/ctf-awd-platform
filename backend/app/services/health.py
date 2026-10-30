import time

from sqlalchemy import select

from ..audit import audit
from ..config import settings
from ..models import HealthCheck, Service, Target, TargetStatus, as_utc, utcnow


async def check_all_targets(db, adapter, broker=None) -> None:
    targets = list((await db.execute(select(Target).where(Target.status != TargetStatus.STOPPED))).scalars())
    for target in targets:
        service = await db.get(Service, target.service_id)
        started = time.monotonic()
        result = await adapter.check_health(target, service)
        duration = int((time.monotonic() - started) * 1000)
        now = utcnow()
        db.add(HealthCheck(
            target_id=target.id,
            status="SUCCESS" if result.ok else "FAILED",
            duration_ms=duration,
            error=result.error,
            checked_at=now,
        ))
        previous_status = target.status
        target.last_health_at = now
        if result.ok:
            target.consecutive_failures = 0
            target.consecutive_successes += 1
            if target.status == TargetStatus.RESTARTING:
                if target.consecutive_successes >= 2:
                    _mark_running(target, now)
            elif target.status in {TargetStatus.UNHEALTHY, TargetStatus.MANUAL_INTERVENTION}:
                if target.consecutive_successes >= 2:
                    _mark_running(target, now)
            elif target.status in {TargetStatus.CREATED, TargetStatus.STARTING}:
                _mark_running(target, now)
        else:
            target.consecutive_successes = 0
            target.consecutive_failures += 1
            if target.consecutive_failures >= 2 and target.status != TargetStatus.MANUAL_INTERVENTION:
                target.status = TargetStatus.UNHEALTHY
                target.unhealthy_since = target.unhealthy_since or now
                try:
                    await _attempt_restart(db, target, now, adapter)
                except Exception as exc:
                    target.status = TargetStatus.MANUAL_INTERVENTION
                    await audit(db, None, "target.restart_failed", "target", target.id, {"error": str(exc)[:500]})
        status_changed = target.status != previous_status
        if status_changed:
            await audit(db, None, "target.status_changed", "target", target.id, {
                "from": previous_status.value,
                "to": target.status.value,
                "error": result.error,
            })
        await db.commit()
        if status_changed and broker:
            await broker.publish("target.status", {"target_id": target.id, "status": target.status.value})


def _mark_running(target: Target, now) -> None:
    if target.unhealthy_since:
        target.total_unhealthy_seconds += max(0, int((now - as_utc(target.unhealthy_since)).total_seconds()))
    target.unhealthy_since = None
    target.status = TargetStatus.RUNNING


async def _attempt_restart(db, target: Target, now, adapter) -> None:
    history = []
    for value in target.restart_history or []:
        from datetime import datetime
        timestamp = datetime.fromisoformat(value)
        if (now - as_utc(timestamp)).total_seconds() <= 300:
            history.append(value)
    target.restart_history = history
    if len(history) >= settings.max_auto_restarts:
        target.status = TargetStatus.MANUAL_INTERVENTION
        await audit(db, None, "target.manual_intervention", "target", target.id, {"restart_count": len(history)})
        return
    target.status = TargetStatus.RESTARTING
    target.restart_history = [*history, now.isoformat()]
    await adapter.restart(target)
    await audit(db, None, "target.auto_restart", "target", target.id, {"volume_preserved": True})
