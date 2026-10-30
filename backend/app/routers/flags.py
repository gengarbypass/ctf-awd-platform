from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_player
from ..models import User
from ..responses import APIError, success
from ..schemas import FlagSubmitRequest
from ..services.scoring import submit_flag


router = APIRouter(prefix="/flags", tags=["flags"])


@router.post("/submit")
async def submit(
    payload: FlagSubmitRequest,
    request: Request,
    user: User = Depends(require_player),
    db: AsyncSession = Depends(get_db),
):
    if not user.team_id:
        raise APIError(409, "TEAM_REQUIRED", "join a team before submitting flags")
    result = await submit_flag(db, user, payload.flag, payload.request_id, request.app.state.events)
    code = result["result"]
    messages = {
        "ACCEPTED": "attack accepted",
        "DUPLICATE": "flag already submitted by this team",
        "OWN_TEAM": "cannot submit your own team's flag",
        "EXPIRED": "flag is expired or inactive",
        "INVALID": "flag is invalid",
        "MATCH_NOT_RUNNING": "match is not running",
    }
    return success(result, code=code, message=messages[code], request_id=payload.request_id)
