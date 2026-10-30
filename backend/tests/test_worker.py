import pytest
from sqlalchemy import select

from app.models import Flag, InjectStatus, MatchStatus, Service, TargetStatus
from app.services.health import check_all_targets
from app.services.rotation import rotate_match
from app.target_adapter import MockTargetAdapter
from conftest import add_flag, make_game


@pytest.mark.asyncio
async def test_rotation_injects_real_mock_files_and_stores_only_hashes(db):
    match, round_, teams, _ = await make_game(db, team_count=2)
    adapter = MockTargetAdapter()
    targets = []
    for index, team in enumerate(teams):
        _, target, service = await add_flag(db, round_, team, f"flag{{old-{index}}}")
        target.status = TargetStatus.CREATED
        await adapter.initialize_target(target, service, team.team_no)
        await adapter.start(target)
        target.status = TargetStatus.RUNNING
        targets.append(target)
    round_.ends_at = match.starts_at
    await db.commit()
    new_round = await rotate_match(db, match, adapter)
    assert new_round.round_no == 2
    flags = (await db.execute(select(Flag).where(Flag.round_id == new_round.id))).scalars().all()
    assert len(flags) == 2
    assert all(flag.inject_status == InjectStatus.ACTIVE for flag in flags)
    assert len({flag.flag_hash for flag in flags}) == 2
    assert all(not flag.flag_hash.startswith("flag{") for flag in flags)
    match.status = MatchStatus.PAUSED
    await db.commit()
    assert await rotate_match(db, match, adapter) is None


@pytest.mark.asyncio
async def test_health_requires_two_failures_and_restarts_preserving_volume(db):
    _, round_, teams, _ = await make_game(db, team_count=1)
    adapter = MockTargetAdapter()
    _, target, service = await add_flag(db, round_, teams[0])
    await adapter.initialize_target(target, service, teams[0].team_no)
    await adapter.start(target)
    volume = target.volume_name
    await adapter.stop(target)
    await check_all_targets(db, adapter)
    assert target.consecutive_failures == 1 and target.status == TargetStatus.RUNNING
    await check_all_targets(db, adapter)
    assert target.status == TargetStatus.RESTARTING
    assert len(target.restart_history) == 1
    assert target.volume_name == volume
    await check_all_targets(db, adapter)
    assert target.status == TargetStatus.RESTARTING
    await check_all_targets(db, adapter)
    assert target.status == TargetStatus.RUNNING


@pytest.mark.asyncio
async def test_health_stops_after_two_restarts_in_five_minutes(db):
    _, round_, teams, _ = await make_game(db, team_count=1)
    adapter = MockTargetAdapter()
    _, target, _ = await add_flag(db, round_, teams[0])
    await adapter.initialize_target(target, service=await db.get(Service, target.service_id), team_no=teams[0].team_no)
    await adapter.start(target)
    await adapter.stop(target)
    for _ in range(4):
        await check_all_targets(db, adapter)
        await adapter.stop(target)
    assert target.status == TargetStatus.MANUAL_INTERVENTION
    assert len(target.restart_history) == 2
    assert target.volume_name == f"volume-{teams[0].team_no}"
