"""
config.py — centralized configuration for the EcoMind AI backend.

No extra dependency (deliberately not using pydantic-settings) so the
project keeps the same short requirements.txt that already installs
cleanly. Every setting can be overridden with an environment variable,
so the same code runs unmodified in dev, test, and production:

    ECOMIND_HOST=0.0.0.0
    ECOMIND_PORT=8000
    ECOMIND_LOG_LEVEL=INFO
    ECOMIND_CORS_ORIGINS=http://localhost:5500,https://example.com
    ECOMIND_KB_PATH=data/kb.json
    ECOMIND_RETRIEVAL_K=3
    ECOMIND_MIN_SCORE=0.05
    ECOMIND_MAX_QUERY_LEN=500
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).parent


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("ECOMIND_HOST", "127.0.0.1")
    port: int = _env_int("ECOMIND_PORT", 8000)
    log_level: str = os.getenv("ECOMIND_LOG_LEVEL", "INFO").upper()
    cors_origins: List[str] = field(
        default_factory=lambda: _env_list("ECOMIND_CORS_ORIGINS", ["*"])
    )
    kb_path: Path = Path(
        os.getenv("ECOMIND_KB_PATH", str(BASE_DIR / "data" / "kb.json"))
    )
    retrieval_k: int = _env_int("ECOMIND_RETRIEVAL_K", 3)
    min_score: float = _env_float("ECOMIND_MIN_SCORE", 0.05)
    max_query_len: int = _env_int("ECOMIND_MAX_QUERY_LEN", 500)

    # Allowed diet categories for the footprint estimator (kept here so
    # validation in app.py and defaults in rag.py never drift apart).
    allowed_diets: tuple = ("meat", "average", "veg", "vegan")


settings = Settings()
