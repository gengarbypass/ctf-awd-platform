import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import MatchStatus, ScoreLedger, Submission, SubmissionResult, Team, utcnow
from app.services.scoring import submit_flag
from conftest import add_flag, make_game


async def scores(db, teams):
    return [(await db.get(Team, team.id)).current_score for team in teams]


@pytest.mark.asyncio
async def test_score_01_valid_attack_updates_both_and_writes_two_ledgers(db):
    match, round_, teams, users = await make_game(db)
    flag, _, _ = await add_flag(db, round_, teams[1])
    result = await submit_flag(db, users[0], "flag{test-valid}", "request-score-01")
    assert result["result"] == "ACCEPTED"
    assert await scores(db, teams[:2]) == [1100, 950]
    ledgers = (await db.execute(select(ScoreLedger).order_by(ScoreLedger.delta.desc()))).scalars().all()
    assert [(item.delta, item.score_after) for item in ledgers] == [(100, 1100), (-50, 950)]
    assert teams[0].attack_count == 1 and teams[1].breached_count == 1


@pytest.mark.asyncio
async def test_score_02_duplicate_does_not_change_scores(db):
    _, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[1])
    await submit_flag(db, users[0], "flag{test-valid}", "request-first")
    result = await submit_flag(db, users[0], "flag{test-valid}", "request-duplicate")
    assert result["result"] == "DUPLICATE"
    assert await scores(db, teams[:2]) == [1100, 950]
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 2


@pytest.mark.asyncio
async def test_score_03_another_team_can_attack_same_flag(db):
    _, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[1])
    await submit_flag(db, users[0], "flag{test-valid}", "request-a")
    result = await submit_flag(db, users[2], "flag{test-valid}", "request-c")
    assert result["result"] == "ACCEPTED"
    assert await scores(db, teams) == [1100, 900, 1100]
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 4


@pytest.mark.asyncio
async def test_score_04_own_team_flag_is_rejected_without_score(db):
    _, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[0])
    result = await submit_flag(db, users[0], "flag{test-valid}", "request-own")
    assert result["result"] == "OWN_TEAM"
    assert await scores(db, teams[:1]) == [1000]
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 0


@pytest.mark.asyncio
async def test_score_05_expired_and_random_flags_do_not_score(db):
    _, round_, teams, users = await make_game(db)
    flag, _, _ = await add_flag(db, round_, teams[1])
    flag.valid_to = utcnow() - timedelta(seconds=1)
    await db.commit()
    expired = await submit_flag(db, users[0], "flag{test-valid}", "request-expired")
    invalid = await submit_flag(db, users[0], "flag{random}", "request-invalid")
    assert expired["result"] == "EXPIRED" and invalid["result"] == "INVALID"
    assert await scores(db, teams[:2]) == [1000, 1000]
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 0


@pytest.mark.asyncio
async def test_score_06_concurrent_same_team_submissions_score_once(db):
    _, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[1])
    results = await asyncio.gather(*[
        submit_flag(db, users[0], "flag{test-valid}", f"request-concurrent-{index}")
        for index in range(10)
    ])
    assert sum(item["result"] == "ACCEPTED" for item in results) == 1
    assert sum(item["result"] == "DUPLICATE" for item in results) == 9
    assert await scores(db, teams[:2]) == [1100, 950]
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 2
    assert await db.scalar(select(func.count(Submission.id)).where(Submission.result == SubmissionResult.ACCEPTED)) == 1


@pytest.mark.asyncio
async def test_score_07_paused_match_rejects_submission(db):
    match, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[1])
    match.status = MatchStatus.PAUSED
    await db.commit()
    result = await submit_flag(db, users[0], "flag{test-valid}", "request-paused")
    assert result["result"] == "MATCH_NOT_RUNNING"
    assert await scores(db, teams[:2]) == [1000, 1000]
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 0


@pytest.mark.asyncio
async def test_score_08_mid_transaction_failure_rolls_back_everything(db, monkeypatch):
    _, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[1])
    original_commit = db.commit

    async def fail_commit():
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated"):
        await submit_flag(db, users[0], "flag{test-valid}", "request-rollback")
    monkeypatch.setattr(db, "commit", original_commit)
    unchanged = (await db.execute(select(Team).where(Team.team_no.in_([1, 2])).order_by(Team.team_no))).scalars().all()
    assert [team.current_score for team in unchanged] == [1000, 1000]
    assert await db.scalar(select(func.count(Submission.id))) == 0
    assert await db.scalar(select(func.count(ScoreLedger.id))) == 0
