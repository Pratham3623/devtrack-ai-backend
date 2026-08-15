"""
Phase 7 — Real-Time Collaboration & WebSockets Test Suite
==========================================================
Verifies WebSocket authentication, connection lifecycle, presence indicators,
typing indicators, and event broadcasting.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User
from app.main import app


async def setup_ws_fixtures(db_session):
    user1 = User(email="ws_user1@devtrack.ai", full_name="WS User 1", role=UserRole.MEMBER, is_active=True)
    user2 = User(email="ws_user2@devtrack.ai", full_name="WS User 2", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user1, user2])
    await db_session.flush()

    org = Organization(name="WS Corp", slug="ws-corp", owner_id=user1.id)
    db_session.add(org)
    await db_session.flush()

    db_session.add_all([
        OrgMember(organization_id=org.id, user_id=user1.id, role=OrgRole.OWNER),
        OrgMember(organization_id=org.id, user_id=user2.id, role=OrgRole.DEVELOPER),
    ])

    proj = Project(organization_id=org.id, name="WS Project", key="WSP", owner_id=user1.id)
    db_session.add(proj)
    await db_session.commit()

    return {
        "user1": user1,
        "user2": user2,
        "org": org,
        "proj": proj,
        "token1": create_access_token(subject=str(user1.id), role=user1.role.value),
        "token2": create_access_token(subject=str(user2.id), role=user2.role.value),
    }


@pytest.mark.asyncio
async def test_websocket_auth_rejection(db_session):
    fix = await setup_ws_fixtures(db_session)
    
    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override

    client = TestClient(app)
    ws_url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ws?token=invalid_token"
    with pytest.raises(Exception):
        with client.websocket_connect(ws_url):
            pass
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_websocket_connect_ping_pong_presence(db_session):
    fix = await setup_ws_fixtures(db_session)

    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override

    client = TestClient(app)
    ws_url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ws?token={fix['token1']}"

    with client.websocket_connect(ws_url) as websocket:
        # Receive initial presence event on connect
        data = websocket.receive_json()
        assert data["event_type"] == "PRESENCE_UPDATE"
        assert len(data["payload"]["users"]) == 1
        assert data["payload"]["users"][0]["name"] == "WS User 1"

        # Send ping
        websocket.send_json({"event_type": "ping"})
        pong_data = websocket.receive_json()
        assert pong_data["event_type"] == "PONG"
        assert pong_data["payload"]["pong"] is True

        # Send typing indicator
        websocket.send_json({
            "event_type": "TYPING_START",
            "issue_id": str(uuid.uuid4()),
        })
        typing_data = websocket.receive_json()
        assert typing_data["event_type"] == "TYPING_START"
        assert typing_data["sender_name"] == "WS User 1"
        assert typing_data["payload"]["is_typing"] is True

    app.dependency_overrides.clear()
