import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models import User, UserRole


def test_password_hashing():
    raw = "MySecurePassword123!"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_creation_and_decoding():
    user_id = str(uuid.uuid4())
    data = {"sub": user_id, "role": "admin"}
    token = create_access_token(data=data, expires_delta=timedelta(minutes=15))
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["role"] == "admin"


def test_jwt_token_invalid():
    assert decode_token("invalid.token.structure") is None
    assert decode_token("") is None


def test_login_success(client: TestClient, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": admin_user["user"].email,
            "password": admin_user["raw_password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == admin_user["user"].email
    assert data["user"]["role"] == "admin"


def test_login_invalid_password(client: TestClient, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": admin_user["user"].email,
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_login_nonexistent_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "nonexistent@example.com",
            "password": "SomePassword123!",
        },
    )
    assert response.status_code == 401


def test_login_inactive_user(client: TestClient, db_session: Session):
    password = "InactivePass123!"
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        full_name="Inactive User",
        role=UserRole.client,
        hashed_password=get_password_hash(password),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "inactive@example.com", "password": password},
    )
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


def test_get_current_user_me(client: TestClient, client_user):
    response = client.get("/api/v1/auth/me", headers=client_user["headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == client_user["user"].email
    assert data["full_name"] == client_user["user"].full_name
    assert data["role"] == "client"


def test_get_current_user_me_unauthorized(client: TestClient):
    # No header
    res1 = client.get("/api/v1/auth/me")
    assert res1.status_code == 401

    # Malformed header
    res2 = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"}
    )
    assert res2.status_code == 401


def test_admin_user_management(client: TestClient, admin_user, client_user):
    # Admin can list users
    res = client.get("/api/v1/users/", headers=admin_user["headers"])
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 2

    # Client user cannot list users (403)
    res_forbidden = client.get("/api/v1/users/", headers=client_user["headers"])
    assert res_forbidden.status_code == 403

    # Admin creates a new client user
    new_user_data = {
        "email": "brandnew@example.com",
        "full_name": "Brand New",
        "role": "client",
        "password": "SecurePassword123!",
    }
    create_res = client.post(
        "/api/v1/users/", json=new_user_data, headers=admin_user["headers"]
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["email"] == "brandnew@example.com"

    # Duplicate email should be rejected
    dup_res = client.post(
        "/api/v1/users/", json=new_user_data, headers=admin_user["headers"]
    )
    assert dup_res.status_code == 400

    # Admin cannot deactivate their own account
    self_deactivate = client.delete(
        f"/api/v1/users/{admin_user['user'].id}", headers=admin_user["headers"]
    )
    assert self_deactivate.status_code == 400
