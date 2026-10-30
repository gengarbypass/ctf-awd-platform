from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .database import get_db
from .models import Role, User, UserStatus
from .responses import APIError


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("awd_session")
    if not token:
        raise APIError(401, "UNAUTHORIZED", "authentication required")
    user_id = await request.app.state.session_store.get(token)
    if not user_id:
        raise APIError(401, "UNAUTHORIZED", "session is invalid or expired")
    user = (await db.execute(select(User).options(selectinload(User.team)).where(User.id == user_id))).scalar_one_or_none()
    if not user or user.status != UserStatus.ACTIVE:
        raise APIError(401, "UNAUTHORIZED", "user is disabled or does not exist")
    return user


def require_roles(*roles: Role):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise APIError(403, "FORBIDDEN", "insufficient permissions")
        return user

    return dependency


require_player = require_roles(Role.PLAYER)
require_admin = require_roles(Role.ADMIN)
