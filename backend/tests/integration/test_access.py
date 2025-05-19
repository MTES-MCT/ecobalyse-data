import urllib
from typing import Any

import pytest
from httpx import AsyncClient
from litestar.exceptions import PermissionDeniedException
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from structlog.testing import capture_logs

from app.config import get_settings
from app.db.models import User
from app.domain.accounts.services import UserService

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("email", "should_send_email", "expected_status_code"),
    (
        ("superuser@example.com", True, 201),
        ("bademail@test.com", False, 201),
    ),
)
async def test_user_magic_link_login(
    client: AsyncClient, email: str, should_send_email: bool, expected_status_code: int
) -> None:
    with capture_logs() as cap_logs:
        response = await client.post(
            "/api/access/magic_link/login", json={"email": email}
        )
        assert response.status_code == expected_status_code

    if should_send_email:
        settings = get_settings()
        print(cap_logs)
        assert any(
            ["demandé un lien de connexion à Ecobalyse" in e["event"] for e in cap_logs]
        )
        assert any(
            [
                f'<p><a href="{settings.email.MAGIC_LINK_URL}/{urllib.parse.quote_plus(email)}/'
                in e["event"]
                for e in cap_logs
            ]
        )
    else:
        assert not any(
            ["demandé un lien de connexion à Ecobalyse" in e["event"] for e in cap_logs]
        )


@pytest.mark.parametrize(
    ("email", "token", "expected_status_code"),
    (
        ("superuser@example1.com", "Test_Password1!_token", 403),
        ("superuser@example.com", "Test_Password1!_token", 201),
        ("user@example.com", "Test_Password1!_token", 403),
        ("user@example.com", "Test_Password2!_token", 201),
        ("inactive@example.com", "Old_Password2!_token", 403),
        ("inactive@example.com", "Old_Password3!_token", 403),
    ),
)
async def test_user_magic_link_validation(
    client: AsyncClient, email: str, token: str, expected_status_code: int
) -> None:
    response = await client.get(
        "/api/access/login", params={"email": email, "token": token}
    )
    assert response.status_code == expected_status_code


async def test_user_login_token_expiration(client: AsyncClient) -> None:
    email = "superuser@example.com"
    token = "Test_Password1!_token"

    response = await client.get(
        "/api/access/login", params={"email": email, "token": token}
    )

    assert response.status_code == 201
    json = response.json()

    assert "access_token" in json
    # Two year expiration
    assert json["expires_in"] == 60 * 60 * 24 * 365 * 2


async def test_user_cant_use_same_token_twice(
    client: AsyncClient,
) -> None:
    email = "superuser@example.com"
    token = "Test_Password1!_token"

    response = await client.get(
        "/api/access/login", params={"email": email, "token": token}
    )

    assert response.status_code == 201

    response = await client.get(
        "/api/access/login", params={"email": email, "token": token}
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("email", "token"),
    (("superuser@example.com", "Test_Password1!_token"),),
)
async def test_user_logout(client: AsyncClient, email: str, token: str) -> None:
    response = await client.get(
        "/api/access/login", params={"email": email, "token": token}
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
    json = response.json()

    assert json == {
        "id": json["id"],
        "email": "user@example.com",
        "profile": {
            "firstName": "Example",
            "lastName": "User",
            "organization": "Example organization",
            "termsAccepted": False,
        },
        "roles": [],
        "isSuperuser": False,
        "isActive": True,
        "isVerified": False,
        "magicLinkSentAt": json["magicLinkSentAt"],
    }


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
            "/api/access/magic_link/signup",
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
                "termsAccepted": True,
            },
            "isSuperuser": False,
            "isActive": True,
            "isVerified": False,
            "magicLinkSentAt": None,
            "roles": [
                {
                    "roleId": json["roles"][0]["roleId"],
                    "roleSlug": "application-access",
                    "roleName": "Application Access",
                    "assignedAt": json["roles"][0]["assignedAt"],
                }
            ],
        }

        user_data = {
            "email": "foo@bar.com",
            "firstName": "first name test",
            "lastName": "last name test",
            "organization": "test organization",
            "termsAccepted": True,
        }
        response = await client.post(
            "/api/access/magic_link/signup",
            json=user_data,
        )

        assert response.status_code == 409

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
