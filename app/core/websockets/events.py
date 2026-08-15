"""
Real-Time Event Schemas & Broadcast DTOs
========================================
Defines standard WebSocket event payloads and helper broadcasting functions.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class WSEventType(str, Enum):
    # Presence & Activity
    PRESENCE_UPDATE = "PRESENCE_UPDATE"
    TYPING_START = "TYPING_START"
    TYPING_STOP = "TYPING_STOP"

    # Board & Issues
    BOARD_UPDATE = "BOARD_UPDATE"
    ISSUE_MOVED = "ISSUE_MOVED"
    ISSUE_CREATED = "ISSUE_CREATED"
    ISSUE_UPDATED = "ISSUE_UPDATED"
    ISSUE_DELETED = "ISSUE_DELETED"

    # Comments
    COMMENT_CREATED = "COMMENT_CREATED"
    COMMENT_DELETED = "COMMENT_DELETED"

    # Notifications
    NOTIFICATION = "NOTIFICATION"

    # System
    PONG = "PONG"
    ERROR = "ERROR"


class WSEvent(BaseModel):
    event_type: WSEventType
    project_id: str
    issue_id: Optional[str] = None
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    timestamp: str
    payload: Dict[str, Any] = Field(default_factory=dict)
