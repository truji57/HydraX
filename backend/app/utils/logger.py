import logging
import sys
from datetime import datetime

from app.config import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_handler: logging.Handler | None = None


def _ensure_handler() -> logging.Handler:
    global _handler
    if _handler is None:
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    return _handler


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    if not logger.handlers:
        logger.addHandler(_ensure_handler())
        logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    if not logger.handlers:
        logger.addHandler(_ensure_handler())
        logger.propagate = False
    return logger
