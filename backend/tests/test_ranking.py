from datetime import timedelta

import pytest

from app.models import TargetStatus
from app.services.ranking import build_live_scoreboard, scoreboard_snapshot
from app.services.scoring import submit_flag
from conftest import add_flag, make_game


@pytest.mark.asyncio
async def test_ranking_uses_all_tiebreakers_and_allows_negative_score(db):
    match, round_, teams, _ = await make_game(db, team_count=8)
    teams[0].current_score = 1200
    teams[1].current_score = teams[2].current_score = 1000
    teams[1].attack_count, teams[2].attack_count = 2, 1
    teams[3].current_score = teams[4].current_score = 900
    teams[5].current_score = teams[6].current_score = 900
    teams[5].last_score_at = match.starts_at
    teams[6].last_score_at = match.starts_at + timedelta(seconds=1)
    teams[7].current_score = -10
    _, slow_target, _ = await add_flag(db, round_, teams[3], "flag{slow}")
    _, fast_target, _ = await add_flag(db, round_, teams[4], "flag{fast}")
    slow_target.total_unhealthy_seconds = 20
    fast_target.total_unhealthy_seconds = 10
    await db.commit()
    board = await build_live_scoreboard(db, match)
    ordered = [row["team_no"] for row in board["teams"]]
    assert ordered == [1, 2, 3, 6, 7, 5, 4, 8]
    assert board["teams"][-1]["score"] == -10


@pytest.mark.asyncio
async def test_frozen_scoreboard_remains_snapshot_while_scoring_continues(db):
    match, round_, teams, users = await make_game(db)
    await add_flag(db, round_, teams[1])
    match.freeze_snapshot = await build_live_scoreboard(db, match)
    match.score_frozen = True
    await db.commit()
    result = await submit_flag(db, users[0], "flag{test-valid}", "request-freeze")
    assert result["result"] == "ACCEPTED"
    frozen = await scoreboard_snapshot(db)
    live = await build_live_scoreboard(db, match)
    assert frozen["frozen"] is True
    assert next(row for row in frozen["teams"] if row["team_no"] == 1)["score"] == 1000
    assert next(row for row in live["teams"] if row["team_no"] == 1)["score"] == 1100
