import pytest
from sqlalchemy import func, select

from app.models import AuditLog, Role, Target, Team, User
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
