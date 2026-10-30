import asyncio
import json
import logging

import asyncssh
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..audit import audit
from ..database import SessionLocal
from ..models import Role, Target, TargetStatus, User, UserStatus
from ..config import settings
from ..security import derive_terminal_password


router = APIRouter(tags=["terminal"])
logger = logging.getLogger("awd.terminal")


@router.websocket("/terminal/{target_id}/ws")
async def terminal_proxy(websocket: WebSocket, target_id: str):
    await websocket.accept()
    user = None
    target = None
    async with SessionLocal() as db:
        token = websocket.cookies.get("awd_session")
        user_id = await websocket.app.state.session_store.get(token) if token else None
        user = await db.get(User, user_id) if user_id else None
        target = await db.get(Target, target_id)
        allowed = bool(
            user
            and user.status == UserStatus.ACTIVE
            and target
            and (user.role == Role.ADMIN or (user.role == Role.PLAYER and user.team_id == target.team_id))
        )
        if not allowed:
            await audit(db, user.id if user else None, "terminal.access_denied", "target", target_id, {
                "owner_team_id": target.team_id if target else None,
            })
            await db.commit()
            await websocket.close(code=4403, reason="terminal access denied")
            return
        await audit(db, user.id, "terminal.connected", "target", target.id)
        await db.commit()

    if target.status == TargetStatus.STOPPED:
        await websocket.close(code=4409, reason="target is stopped")
        return

    connection = None
    process = None
    try:
        options = {
            "host": target.gateway_host,
            "port": target.gateway_port,
            "username": settings.terminal_ssh_username,
            "known_hosts": None,
            "encoding": None,
        }
        options["password"] = derive_terminal_password(target.team_id)
        connection = await asyncssh.connect(**options)
        process = await connection.create_process(term_type="xterm-256color", term_size=(120, 32), stderr=asyncssh.STDOUT)

        async def ssh_to_ws():
            while True:
                data = await process.stdout.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)

        async def ws_to_ssh():
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    process.stdin.write(message["bytes"])
                elif message.get("text") is not None:
                    text = message["text"]
                    try:
                        control = json.loads(text)
                    except json.JSONDecodeError:
                        control = None
                    if isinstance(control, dict) and control.get("type") == "resize":
                        process.change_terminal_size(int(control["cols"]), int(control["rows"]))
                    elif isinstance(control, dict) and control.get("type") == "input":
                        process.stdin.write(str(control.get("data", "")).encode())
                    else:
                        process.stdin.write(text.encode())

        tasks = [asyncio.create_task(ssh_to_ws()), asyncio.create_task(ws_to_ssh())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    except (asyncssh.Error, OSError, WebSocketDisconnect) as exc:
        logger.warning("terminal connection failed for target %s: %s", target_id, exc)
        try:
            await websocket.close(code=1011, reason="terminal connection failed")
        except RuntimeError:
            pass
    finally:
        if process:
            process.close()
        if connection:
            connection.close()
            await connection.wait_closed()
        async with SessionLocal() as db:
            await audit(db, user.id, "terminal.disconnected", "target", target.id)
            await db.commit()
