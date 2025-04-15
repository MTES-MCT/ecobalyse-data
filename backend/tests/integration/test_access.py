import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("username", "password", "expected_status_code"),
    (
        ("superuser@example1.com", "Test_Password1!", 403),
        ("superuser@example.com", "Test_Password1!", 201),
        ("user@example.com", "Test_Password1!", 403),
        ("user@example.com", "Test_Password2!", 201),
        ("inactive@example.com", "Old_Password2!", 403),
        ("inactive@example.com", "Old_Password3!", 403),
    ),
)
async def test_user_login(
    client: AsyncClient, username: str, password: str, expected_status_code: int
) -> None:
    response = await client.post(
        "/api/access/login", data={"username": username, "password": password}
    )
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    ("username", "password"),
    (("superuser@example.com", "Test_Password1!"),),
)
async def test_user_logout(client: AsyncClient, username: str, password: str) -> None:
    response = await client.post(
        "/api/access/login", data={"username": username, "password": password}
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
    user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    user_data = {"email": "foo@bar.com", "password": "test"}
    response = await client.post(
        "/api/access/signup",
        headers=user_token_headers,
        json=user_data,
    )

    # Only superusers should be able to create a new user
    assert response.status_code == 403

    response = await client.post(
        "/api/access/signup", headers=superuser_token_headers, json=user_data
    )

    # Only superusers should be able to create a new user
    assert response.status_code == 201
    json = response.json()

    assert json == {
        "id": json["id"],
        "email": "foo@bar.com",
        "name": None,
        "isSuperuser": False,
        "isActive": True,
        "isVerified": False,
        "hasPassword": True,
        "roles": [],
    }
