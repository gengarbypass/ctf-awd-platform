from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, MatchStatus, Role, Service, Target, Team, User, utcnow
from app.security import hash_password
from conftest import add_flag, make_game


async def login(client, username="player1", password="Player123!"):
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


@pytest.mark.asyncio
async def test_player_cannot_access_admin_api_or_change_data(client):
    http, db = client
    await make_game(db)
    await db.commit()
    await login(http)
    before = await db.scalar(select(func.count(Team.id)))
    response = await http.post("/api/v1/admin/teams", json={"team_no": 10, "name": "Forbidden", "invite_code": "NOPE-10"})
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert await db.scalar(select(func.count(Team.id))) == before


@pytest.mark.asyncio
async def test_admin_cannot_submit_flag_and_unauthenticated_is_rejected(client):
    http, db = client
    _, round_, teams, _ = await make_game(db)
    await add_flag(db, round_, teams[1])
    db.add(User(username="admin", password_hash=hash_password("Admin123!"), role=Role.ADMIN))
    await db.commit()
    await login(http, "admin", "Admin123!")
    response = await http.post("/api/v1/flags/submit", json={"flag": "flag{test-valid}", "request_id": "admin-request"})
    assert response.status_code == 403
    http.cookies.clear()
    response = await http.get("/api/v1/admin/teams")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_team_restart_is_denied_and_audited(client):
    http, db = client
    _, round_, teams, _ = await make_game(db)
    _, target, _ = await add_flag(db, round_, teams[1])
    await login(http)
    response = await http.post(f"/api/v1/targets/{target.id}/restart")
    assert response.status_code == 403
    denial = (await db.execute(select(AuditLog).where(AuditLog.action == "target.restart_denied"))).scalar_one()
    assert denial.object_id == target.id
    assert target.status.value == "RUNNING"


@pytest.mark.asyncio
async def test_registration_enforces_team_capacity(client):
    http, db = client
    _, _, teams, _ = await make_game(db, team_count=1)
    for index in range(2, 5):
        db.add(User(username=f"extra{index}", password_hash=hash_password("Player123!"), role=Role.PLAYER, team_id=teams[0].id))
    await db.commit()
    response = await http.post("/api/v1/auth/register", json={"username": "fifth", "password": "Player123!", "invite_code": "INVITE-1"})
    assert response.status_code == 409
    assert response.json()["code"] == "TEAM_FULL"


@pytest.mark.asyncio
async def test_player_sees_only_opponent_public_targets(client):
    http, db = client
    _, round_, teams, _ = await make_game(db, team_count=3)
    _, own_target, _ = await add_flag(db, round_, teams[0], "flag{own-team}")
    _, opponent_target, _ = await add_flag(db, round_, teams[1], "flag{opponent-team}")
    await login(http)

    response = await http.get("/api/v1/targets/opponents")
    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [opponent_target.id]
    assert items[0]["team_id"] == teams[1].id
    assert items[0]["public_port"] == opponent_target.public_port
    assert "attack_ip" not in items[0]
    assert "container_name" not in items[0]
    assert "gateway_host" not in items[0]
    assert own_target.id != items[0]["id"]


@pytest.mark.asyncio
async def test_next_match_resets_team_scores(client):
    http, db = client
    previous_match, _, teams, _ = await make_game(db)
    previous_match.status = MatchStatus.FINISHED
    teams[0].current_score = 1550
    teams[0].attack_count = 7
    teams[0].breached_count = 3
    team_id = teams[0].id
    db.add(User(username="admin", password_hash=hash_password("Admin123!"), role=Role.ADMIN))
    await db.commit()
    await login(http, "admin", "Admin123!")

    start = utcnow() + timedelta(minutes=5)
    response = await http.post("/api/v1/admin/matches", json={
        "name": "Next Match",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=2)).isoformat(),
        "round_seconds": 300,
        "grace_seconds": 30,
    })
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "DRAFT"
    db.expire_all()
    reset_team = await db.get(Team, team_id)
    assert reset_team.current_score == 1000
    assert reset_team.attack_count == 0
    assert reset_team.breached_count == 0
    reset_audit = (await db.execute(select(AuditLog).where(AuditLog.action == "match.scores_reset"))).scalar_one()
    assert reset_audit.detail["reason"] == "new match"


@pytest.mark.asyncio
async def test_admin_can_reset_current_match_scores_before_start(client):
    http, db = client
    match, _, teams, _ = await make_game(db)
    match.status = MatchStatus.DRAFT
    teams[0].current_score = 1700
    teams[0].attack_count = 9
    team_id = teams[0].id
    db.add(User(username="admin", password_hash=hash_password("Admin123!"), role=Role.ADMIN))
    await db.commit()
    await login(http, "admin", "Admin123!")

    response = await http.post("/api/v1/admin/match/reset-scores", json={})
    assert response.status_code == 200
    assert response.json()["data"]["teams"] == 3
    db.expire_all()
    reset_team = await db.get(Team, team_id)
    assert reset_team.current_score == 1000
    assert reset_team.attack_count == 0


@pytest.mark.asyncio
async def test_admin_can_delete_player_without_submissions(client):
    http, db = client
    _, _, _, users = await make_game(db)
    admin = User(username="admin", password_hash=hash_password("Admin123!"), role=Role.ADMIN)
    db.add(admin)
    victim = users[0]
    db.add(AuditLog(actor_id=victim.id, action="test.before_delete", object_type="user", object_id=victim.id))
    await db.commit()
    await login(http, "admin", "Admin123!")

    response = await http.delete(f"/api/v1/admin/users/{victim.id}")
    assert response.status_code == 200
    assert await db.scalar(select(func.count(User.id)).where(User.id == victim.id)) == 0
    before = (await db.execute(select(AuditLog).where(AuditLog.action == "test.before_delete"))).scalar_one()
    assert before.actor_id is None
    deleted = (await db.execute(select(AuditLog).where(AuditLog.action == "user.delete"))).scalar_one()
    assert deleted.object_id == victim.id
    assert deleted.actor_id == admin.id


@pytest.mark.asyncio
async def test_admin_can_force_delete_service_with_targets(client):
    http, db = client
    _, _, teams, _ = await make_game(db, team_count=1)
    service = Service(
        code="cleanup",
        name="Cleanup",
        service_no=9,
        protocol="TCP",
        internal_port=8080,
        public_base_port=21000,
        flag_path="/data/flag",
        image="cleanup:test",
    )
    db.add(service)
    await db.flush()
    target = Target(
        team_id=teams[0].id,
        service_id=service.id,
        container_name="cleanup-target",
        attack_ip="172.31.1.99",
        public_port=29999,
        volume_name="cleanup-target-data",
        gateway_host="gateway-t01",
        gateway_port=2222,
    )
    db.add(target)
    admin = User(username="admin", password_hash=hash_password("Admin123!"), role=Role.ADMIN)
    db.add(admin)
    await db.commit()
    await login(http, "admin", "Admin123!")

    refused = await http.delete(f"/api/v1/admin/services/{service.id}")
    assert refused.status_code == 409
    assert refused.json()["code"] == "SERVICE_IN_USE"

    response = await http.delete(f"/api/v1/admin/services/{service.id}?force=true")
    assert response.status_code == 200
    assert await db.scalar(select(func.count(Service.id)).where(Service.id == service.id)) == 0
    assert await db.scalar(select(func.count(Target.id)).where(Target.id == target.id)) == 0
