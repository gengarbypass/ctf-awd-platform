from fastapi import FastAPI

from .main import lifespan
from .routers.terminal import router


terminal_app = FastAPI(title="AWD Terminal Proxy", version="1.0.0", lifespan=lifespan)
terminal_app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.terminal_server:terminal_app", host="127.0.0.1", port=8001)
