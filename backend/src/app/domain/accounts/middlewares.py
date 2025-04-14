import requests
from app.config import get_settings
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)

COOKIE_HEADER = "Cookie"


class DjangoAuthenticationMiddleware(AbstractAuthenticationMiddleware):
    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        """Given a request, parse the bearer token stored in the header and retrieve the user correlating to the token from the Django API"""

        # retrieve the auth header
        auth_header = connection.headers.get(COOKIE_HEADER)
        if not auth_header:
            raise NotAuthorizedException()

        settings = get_settings()

        """Authenticate a user against Django API using the Cookie Auth of Django."""
        response = requests.get(
            settings.auth.AUTH_ENDPOINT, headers={COOKIE_HEADER: auth_header}
        )
        user = response.json()
        if response.status_code != 200 or not user["staff"]:
            raise NotAuthorizedException()

        connection.set_session(user)

        return AuthenticationResult(user=user, auth=user["token"])
