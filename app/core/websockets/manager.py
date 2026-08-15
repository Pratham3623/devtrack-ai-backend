"""
WebSocket Connection & Redis Pub/Sub Manager
=============================================
Manages active WebSocket client connections per project room and handles
Redis Pub/Sub broadcasting for horizontal scaling across worker instances.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from fastapi import WebSocket

from app.core.logging import logger
from app.core.redis import redis_client
from app.core.websockets.events import WSEvent, WSEventType


class ConnectionManager:
    def __init__(self):
        # project_id -> Set[Tuple[WebSocket, user_id, user_name]]
        self.active_connections: Dict[str, Set[Tuple[WebSocket, str, str]]] = {}
        # Track presence: project_id -> {user_id: {"name": name, "viewing_issue_id": None, "last_seen": timestamp}}
        self.presence_state: Dict[str, Dict[str, dict]] = {}
        # Pub/Sub background listener task
        self.pubsub_task: Optional[asyncio.Task] = None
        self._subscribed_channels: Set[str] = set()

    async def connect(self, websocket: WebSocket, project_id: str, user_id: str, user_name: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
            self.presence_state[project_id] = {}

        self.active_connections[project_id].add((websocket, user_id, user_name))

        # Track presence
        self.presence_state[project_id][user_id] = {
            "user_id": user_id,
            "name": user_name,
            "viewing_issue_id": None,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"WS client connected: user={user_name} ({user_id}) to project={project_id}")

        # Broadcast updated presence list to room
        await self.broadcast_presence(project_id)

    async def disconnect(self, websocket: WebSocket, project_id: str, user_id: str, user_name: str):
        if project_id in self.active_connections:
            # Remove connection
            self.active_connections[project_id] = {
                conn for conn in self.active_connections[project_id] if conn[0] != websocket
            }

            # Check if user has no remaining active connections in this project room
            has_other_connections = any(
                conn[1] == user_id for conn in self.active_connections[project_id]
            )

            if not has_other_connections:
                if user_id in self.presence_state.get(project_id, {}):
                    del self.presence_state[project_id][user_id]

            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
                if project_id in self.presence_state:
                    del self.presence_state[project_id]

        logger.info(f"WS client disconnected: user={user_name} ({user_id}) from project={project_id}")
        await self.broadcast_presence(project_id)

    async def update_presence_issue(self, project_id: str, user_id: str, issue_id: Optional[str]):
        """Update what issue a user is currently viewing."""
        if project_id in self.presence_state and user_id in self.presence_state[project_id]:
            self.presence_state[project_id][user_id]["viewing_issue_id"] = issue_id
            self.presence_state[project_id][user_id]["last_seen"] = datetime.now(timezone.utc).isoformat()
            await self.broadcast_presence(project_id)

    async def broadcast_presence(self, project_id: str):
        """Broadcast current room presence list."""
        presence_list = list(self.presence_state.get(project_id, {}).values())
        event = WSEvent(
            event_type=WSEventType.PRESENCE_UPDATE,
            project_id=project_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload={"users": presence_list},
        )
        await self.broadcast_event(project_id, event)

    async def broadcast_event(self, project_id: str, event: WSEvent):
        """
        Publish event to Redis Pub/Sub channel for multi-node fan-out,
        and send to local connected websockets directly as fallback.
        """
        message_data = event.model_dump_json()
        channel_name = f"devtrack:events:{project_id}"

        # 1. Publish to Redis if available
        if redis_client is not None:
            try:
                await redis_client.publish(channel_name, message_data)
            except Exception as e:
                logger.warning(f"Failed to publish WS event to Redis: {e}")
                await self._local_broadcast(project_id, message_data)
        else:
            # Fallback to local in-memory broadcast
            await self._local_broadcast(project_id, message_data)

    async def _local_broadcast(self, project_id: str, message_str: str):
        """Send message string directly to all local WebSockets in project room."""
        connections = self.active_connections.get(project_id, set())
        to_remove = set()

        for ws, u_id, u_name in connections:
            try:
                await ws.send_text(message_str)
            except Exception as e:
                logger.warning(f"Error sending WS message to {u_name}: {e}")
                to_remove.add((ws, u_id, u_name))

        for conn in to_remove:
            connections.discard(conn)


# Global singleton instance
manager = ConnectionManager()
