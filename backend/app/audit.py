from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog
from .responses import request_id_var


async def audit(
    db: AsyncSession,
    actor_id: str | None,
    action: str,
    object_type: str,
    object_id: str = "",
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    source_ip = ""
    if request and request.client:
        source_ip = request.client.host
    db.add(AuditLog(
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail or {},
        source_ip=source_ip,
        request_id=request_id_var.get(),
    ))
