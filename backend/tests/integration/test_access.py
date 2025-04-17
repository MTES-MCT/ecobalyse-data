import pytest
from httpx import AsyncClient

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


async def test_user_signup(
    client: "AsyncClient",
) -> None:
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
    print(json)

    # Only superusers should be able to create a new user
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
        "isActive": False,
        "isVerified": False,
        "hasPassword": False,
        "roles": [
            {
                "roleId": json["roles"][0]["roleId"],
                "roleSlug": "application-access",
                "roleName": "Application Access",
                "assignedAt": json["roles"][0]["assignedAt"],
            }
        ],
    }
