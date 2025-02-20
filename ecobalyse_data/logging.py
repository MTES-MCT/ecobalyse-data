import logging

from rich.logging import RichHandler


def get_logger(name):
    # Use rich for logging
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = RichHandler(markup=True)
    handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
    logger.addHandler(handler)

    return logger
