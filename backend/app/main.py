import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .database import dispose_database
from .events import create_event_broker
from .responses import APIError, api_error_handler, envelope, new_request_id, request_id_var
from .routers import admin, auth, flags, public, targets, terminal
from .sessions import create_session_store
from .target_adapter import create_target_adapter


from .logging_config import configure_logging
configure_logging()
logger = logging.getLogger("awd.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    broker = await create_event_broker()
    app.state.events = broker
    app.state.session_store = create_session_store(broker)
    app.state.target_adapter = create_target_adapter()
    try:
        yield
    finally:
        await broker.close()
        await dispose_database()


app = FastAPI(title="AWD Platform API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied[:80] if supplied else new_request_id()
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


app.add_exception_handler(APIError, api_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder(envelope({"errors": exc.errors()}, "VALIDATION_ERROR", "request validation failed")))


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content=envelope(code="HTTP_ERROR", message=str(exc.detail)))


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("unhandled request error", extra={"request_id": request_id_var.get()})
    return JSONResponse(status_code=500, content=envelope(code="INTERNAL_ERROR", message="internal server error"))


@app.get("/api/v1/health")
async def health():
    from .responses import success
    return success({"status": "ok"})


app.include_router(auth.router, prefix="/api/v1")
app.include_router(public.router, prefix="/api/v1")
app.include_router(flags.router, prefix="/api/v1")
app.include_router(targets.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(terminal.router, prefix="/api/v1")
