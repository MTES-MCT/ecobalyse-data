import logging

from rich.logging import RichHandler

logger = logging.getLogger(__name__)
level = logging.INFO

logger.setLevel(level)

handler = RichHandler(markup=False)
handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logger.addHandler(handler)
