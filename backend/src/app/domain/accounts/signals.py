from __future__ import annotations

import urllib.parse

import emails
import structlog
from emails.template import JinjaTemplate as T
from litestar.events import listener

from app.config import get_settings

logger = structlog.get_logger()


@listener("send_magic_link_email")
async def send_magic_link_email_event_handler(
    email: str,
    token: str,
) -> None:
    """Executes when a login link is asked

    Args:
        email: The email we should send the magic link to
    """
    await logger.adebug(f"Sending magic link email to {email}")
    settings = get_settings()

    message = emails.html(
        subject=T("Connexion à Ecobalyse"),
        html=T(
            '<p>Magic link <a href="http://test.com/api/access/login?username={{ email }}&token={{ token }}">login</a></p>'
        ),
        text=T(
            "Magic link: http://test.com/api/access/login?username={{ email }}&token={{ token }}"
        ),
        mail_from=("Ecobalyse", "ecobalyse@test.com"),
    )

    message.send(
        to=("Test user", email),
        render={
            "email": urllib.parse.quote_plus(email),
            "token": urllib.parse.quote_plus(token),
        },
    )

    if settings.email.SERVER_HOST is None:
        await logger.adebug("No email SERVER_HOST configured don’t send the email.")
        print(message.html_body)
        print(message.text_body)
