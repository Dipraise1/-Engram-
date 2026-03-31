"""Engram — Logging setup."""

import sys
from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - {message}",
        colorize=True,
    )
    logger.add(
        "logs/engram_{time}.log",
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        compression="gz",
    )
