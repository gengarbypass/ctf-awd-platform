from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..audit import audit
from ..database import get_db
from ..dependencies import get_current_user
from ..models import Role, Team, TeamStatus, User, UserStatus, utcnow
from ..responses import APIError, success
from ..schemas import LoginRequest, RegisterRequest
from ..security import hash_password, new_session_token, verify_password
from ..serializers import user_dict


router = APIRouter(prefix="/auth", tags=["auth"])


async def create_session(request: Request, response: Response, user: User) -> None:
    token = new_session_token()
    await request.app.state.session_store.set(token, user.id)
    from ..config import settings
    response.set_cookie(
        "awd_session",
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_secure_cookie,
        samesite="lax",
        path="/",
    )


@router.post("/register")
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    team = (await db.execute(select(Team).where(Team.invite_code == payload.invite_code).with_for_update())).scalar_one_or_none()
    if not team or team.status != TeamStatus.ACTIVE:
        raise APIError(400, "INVALID_INVITE_CODE", "invite code is invalid")
    member_count = await db.scalar(select(func.count(User.id)).where(
        User.team_id == team.id,
        User.role == Role.PLAYER,
        User.status == UserStatus.ACTIVE,
    ))
    if (member_count or 0) >= 4:
        raise APIError(409, "TEAM_FULL", "team already has four players")
    if await db.scalar(select(User.id).where(User.username == payload.username)):
        raise APIError(409, "USERNAME_EXISTS", "username already exists")
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=Role.PLAYER, team_id=team.id)
    db.add(user)
    await db.flush()
    await audit(db, user.id, "auth.register", "user", user.id, {"team_id": team.id}, request)
    await db.commit()
    user.team = team
    response = success(user_dict(user), message="registration successful")
    await create_session(request, response, user)
    return response


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).options(selectinload(User.team)).where(User.username == payload.username))).scalar_one_or_none()
    if not user or not verify_password(user.password_hash, payload.password) or user.status != UserStatus.ACTIVE:
        await audit(db, user.id if user else None, "auth.login_failed", "user", user.id if user else "", {"username": payload.username}, request)
        await db.commit()
        raise APIError(401, "INVALID_CREDENTIALS", "invalid username or password")
    user.last_login_at = utcnow()
    await audit(db, user.id, "auth.login", "user", user.id, request=request)
    await db.commit()
    response = success(user_dict(user), message="login successful")
    await create_session(request, response, user)
    return response


@router.post("/logout")
async def logout(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("awd_session")
    if token:
        await request.app.state.session_store.delete(token)
    await audit(db, user.id, "auth.logout", "user", user.id, request=request)
    await db.commit()
    response = success(message="logout successful")
    response.delete_cookie("awd_session", path="/")
    return response
