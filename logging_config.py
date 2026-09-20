"""
logging_config.py — structured console logging for EcoMind AI.

Every request gets one line with method, path, status, and duration;
every error gets a full traceback. Log level is controlled by
ECOMIND_LOG_LEVEL (see config.py).
"""

import logging
import sys

from config import settings


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("ecomind")

    # Avoid duplicate handlers if this module is imported more than once
    # (e.g. by both app.py and the test suite).
    if logger.handlers:
        return logger

    level = getattr(logging, settings.log_level, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = configure_logging()
