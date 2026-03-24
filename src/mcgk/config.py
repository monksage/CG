"""
MCGK configuration — all settings via environment variables.

MCGK_PORT              – HTTP port (default 6245)
MCGK_HOST              – Bind address (default 0.0.0.0)
MCGK_DB_PATH           – SQLite database path (default ./mcgk.db)
MCGK_HEALTH_INTERVAL   – Health-check interval in seconds (default 10)
MCGK_PROXY_TIMEOUT     – Proxy request timeout in seconds (default 30)
MCGK_STREAM_TIMEOUT    – Read timeout for streaming responses in seconds (default 300)
MCGK_TRUST_ENV         – Whether httpx should trust env vars like HTTP_PROXY (default false)
MCGK_LOG_LEVEL         – Uvicorn log level (default info)
"""

from __future__ import annotations

import os
from pathlib import Path


def _bool(val: str) -> bool:
    return val.lower() in ("1", "true", "yes")


PORT: int = int(os.getenv("MCGK_PORT", "6245"))
HOST: str = os.getenv("MCGK_HOST", "0.0.0.0")
DB_PATH: Path = Path(os.getenv("MCGK_DB_PATH", "mcgk.db"))
HEALTH_INTERVAL: int = int(os.getenv("MCGK_HEALTH_INTERVAL", "10"))
PROXY_TIMEOUT: int = int(os.getenv("MCGK_PROXY_TIMEOUT", "30"))
STREAM_TIMEOUT: int = int(os.getenv("MCGK_STREAM_TIMEOUT", "300"))
TRUST_ENV: bool = _bool(os.getenv("MCGK_TRUST_ENV", "false"))
LOG_LEVEL: str = os.getenv("MCGK_LOG_LEVEL", "info")
