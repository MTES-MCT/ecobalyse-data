from __future__ import annotations

import structlog
from litestar.events import listener

logger = structlog.get_logger()


@listener("send_magic_link_email")
async def send_magic_link_email_event_handler(
    email: str,
) -> None:
    """Executes when a login link is asked

    Args:
        email: The email we should send the magic link to
    """
    await logger.adebug(f"Sending magic link email to {email}")
