import contextvars
import uuid
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def new_request_id() -> str:
    return uuid.uuid4().hex


def envelope(data: Any = None, code: str = "OK", message: str = "success", request_id: str | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data if data is not None else {},
        "request_id": request_id or request_id_var.get() or new_request_id(),
    }


def success(data: Any = None, code: str = "OK", message: str = "success", request_id: str | None = None) -> JSONResponse:
    return JSONResponse(jsonable_encoder(envelope(data, code, message, request_id)))


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(envelope(exc.data, exc.code, exc.message)),
    )
