"""
WebSocket Real-Time API Controller
===================================
Handles real-time WebSocket connections, authentication, presence,
typing indicators, and event routing.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.logging import logger
from app.core.security import decode_access_token
from app.core.websockets.events import WSEvent, WSEventType
from app.core.websockets.manager import manager
from app.db.session import AsyncSessionLocal, get_db
from app.domain.models.user import User

router = APIRouter()


async def get_ws_user(token: str) -> Optional[User]:
    """Validate access token from query string for WebSocket connection."""
    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            return None
        user_uuid = uuid.UUID(user_id_str)

        # Check if get_db dependency is overridden (e.g. during test suite execution)
        from app.main import app
        override = app.dependency_overrides.get(get_db)
        if override:
            res = override()
            if hasattr(res, "__anext__"):
                db = await res.__anext__()
            elif hasattr(res, "__next__"):
                db = next(res)
            else:
                db = res
            stmt = select(User).where(User.id == user_uuid)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user
        else:
            async with AsyncSessionLocal() as session:
                stmt = select(User).where(User.id == user_uuid)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user
    except Exception as e:
        logger.warning(f"WS auth failed: {e}")
        return None
    return None


@router.websocket("/{org_id}/projects/{project_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    token: str = Query(...),
):
    """
    Real-Time Collaboration WebSocket Endpoint
    -------------------------------------------
    - Authenticates user via query parameter `?token=...`
    - Maintains live presence, typing indicators, and room broadcasts
    """
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    proj_id_str = str(project_id)
    user_id_str = str(user.id)
    user_name = user.full_name or user.email

    await manager.connect(websocket, proj_id_str, user_id_str, user_name)

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                event_type = msg.get("event_type")

                if event_type == "ping":
                    pong = WSEvent(
                        event_type=WSEventType.PONG,
                        project_id=proj_id_str,
                        sender_id=user_id_str,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        payload={"pong": True},
                    )
                    await websocket.send_text(pong.model_dump_json())

                elif event_type in ("TYPING_START", "TYPING_STOP"):
                    issue_id = msg.get("issue_id")
                    typing_event = WSEvent(
                        event_type=WSEventType(event_type),
                        project_id=proj_id_str,
                        issue_id=issue_id,
                        sender_id=user_id_str,
                        sender_name=user_name,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        payload={"is_typing": (event_type == "TYPING_START")},
                    )
                    await manager.broadcast_event(proj_id_str, typing_event)

                elif event_type == "PRESENCE_UPDATE":
                    issue_id = msg.get("issue_id")
                    await manager.update_presence_issue(proj_id_str, user_id_str, issue_id)

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket, proj_id_str, user_id_str, user_name)
    except Exception as e:
        logger.error(f"WS error: {e}")
        await manager.disconnect(websocket, proj_id_str, user_id_str, user_name)
