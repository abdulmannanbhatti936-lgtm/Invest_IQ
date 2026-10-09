"""
require_admin (core/deps.py) on a test-only route.

The route lives on a throwaway FastAPI app built here, never on the real app. Phase 9
(Step 9.4) must still test every real admin endpoint.
"""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.deps import require_admin
from models.user import User, UserRole

probe_app = FastAPI()


@probe_app.get("/admin-probe")
def admin_probe(admin: User = Depends(require_admin)):
    return {"ok": True, "email": admin.email}


@pytest.fixture
def probe():
    return TestClient(probe_app)


def _token(client, db, role: UserRole) -> str:
    email = f"role_{role.value}_{uuid.uuid4()}@example.com"
    client.post(
        "/auth/register", json={"email": email, "full_name": "Role Test", "password": "password123"}
    )
    if role == UserRole.admin:
        db.query(User).filter(User.email == email).update({"role": UserRole.admin})
        db.commit()
    return client.post("/auth/login", data={"username": email, "password": "password123"}).json()[
        "access_token"
    ]


def test_admin_gets_200(client, db, probe):
    response = probe.get(
        "/admin-probe", headers={"Authorization": f"Bearer {_token(client, db, UserRole.admin)}"}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_non_admin_gets_403(client, db, probe):
    response = probe.get(
        "/admin-probe", headers={"Authorization": f"Bearer {_token(client, db, UserRole.user)}"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Admin only"}


def test_no_token_gets_401(probe):
    assert probe.get("/admin-probe").status_code == 401
    assert (
        probe.get("/admin-probe", headers={"Authorization": "Bearer not-a-token"}).status_code
        == 401
    )


def test_probe_route_is_not_on_the_real_app(client):
    assert client.get("/admin-probe").status_code == 404
