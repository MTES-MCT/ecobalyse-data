from typing import Any

import pytest
from httpx import AsyncClient
from litestar.exceptions import PermissionDeniedException
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from structlog.testing import capture_logs

from app.db.models import User
from app.domain.accounts.services import UserService

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("username", "token", "expected_status_code"),
    (
        ("superuser@example1.com", "Test_Password1!_token", 403),
        ("superuser@example.com", "Test_Password1!_token", 201),
        ("user@example.com", "Test_Password1!_token", 403),
        ("user@example.com", "Test_Password2!_token", 201),
        ("inactive@example.com", "Old_Password2!_token", 403),
        ("inactive@example.com", "Old_Password3!_token", 403),
    ),
)
async def test_user_login(
    client: AsyncClient, username: str, token: str, expected_status_code: int
) -> None:
    response = await client.get(
        "/api/access/login", params={"username": username, "token": token}
    )
    assert response.status_code == expected_status_code


async def test_user_login_token_expiration(client: AsyncClient) -> None:
    username = "superuser@example.com"
    token = "Test_Password1!_token"

    response = await client.get(
        "/api/access/login", params={"username": username, "token": token}
    )

    assert response.status_code == 201
    json = response.json()

    assert "access_token" in json
    # Two year expiration
    assert json["expires_in"] == 60 * 60 * 24 * 365 * 2


async def test_user_cant_use_same_token_twice(
    client: AsyncClient,
) -> None:
    username = "superuser@example.com"
    token = "Test_Password1!_token"

    response = await client.get(
        "/api/access/login", params={"username": username, "token": token}
    )

    assert response.status_code == 201

    response = await client.get(
        "/api/access/login", params={"username": username, "token": token}
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("username", "token"),
    (("superuser@example.com", "Test_Password1!_token"),),
)
async def test_user_logout(client: AsyncClient, username: str, token: str) -> None:
    response = await client.get(
        "/api/access/login", params={"username": username, "token": token}
    )
    assert response.status_code == 201
    cookies = dict(response.cookies)

    assert cookies.get("token") is not None

    me_response = await client.get("/api/me")
    assert me_response.status_code == 200

    response = await client.post("/api/access/logout")
    assert response.status_code == 200

    # the user can no longer access the /me route.
    me_response = await client.get("/api/me")
    assert me_response.status_code == 401


async def test_user_profile(
    client: "AsyncClient", user_token_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/api/me",
        headers=user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


async def test_user_signup_and_login(
    client: "AsyncClient",
    superuser_token_headers: dict[str, str],
) -> None:
    with capture_logs() as cap_logs:
        user_data = {
            "email": "foo@bar.com",
            "firstName": "first name test",
            "lastName": "last name test",
            "organization": "test organization",
            "termsAccepted": True,
        }
        response = await client.post(
            "/api/access/signup_magic_link",
            json=user_data,
        )

        json = response.json()

        assert response.status_code == 201

        assert json == {
            "id": json["id"],
            "email": "foo@bar.com",
            "profile": {
                "firstName": "first name test",
                "lastName": "last name test",
                "organization": "test organization",
            },
            "isSuperuser": False,
            "isActive": True,
            "isVerified": False,
            "magicLinkSentAt": None,
            "hasPassword": False,
            "roles": [
                {
                    "roleId": json["roles"][0]["roleId"],
                    "roleSlug": "application-access",
                    "roleName": "Application Access",
                    "assignedAt": json["roles"][0]["assignedAt"],
                }
            ],
            "termsAccepted": True,
        }

    assert {
        "event": "Sending magic link email to foo@bar.com",
        "log_level": "debug",
    } in cap_logs


async def test_magic_link_expiration(
    session: AsyncSession,
    raw_users: list[User | dict[str, Any]],
) -> None:
    async with UserService.new(session) as users_service:
        # Magic link login is ok
        authenticated_user = await users_service.authenticate_magic_token(
            raw_users[1]["email"], "Test_Password2!_token"
        )
        assert authenticated_user.magic_link_sent_at is None
        assert authenticated_user.magic_link_hashed_token is None

        # Magic link is outdated 24H duration by default
        with pytest.raises(PermissionDeniedException, match="Magic link token expired"):
            authenticated_user = await users_service.authenticate_magic_token(
                raw_users[2]["email"], "Test_Password3!_token"
            )

        # Magic link was not generated
        with pytest.raises(
            PermissionDeniedException, match="User not found or password invalid"
        ):
            authenticated_user = await users_service.authenticate_magic_token(
                raw_users[3]["email"], ""
            )
