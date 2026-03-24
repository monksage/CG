"""
Shared test fixtures for MCGK test suite.

Provides:
  - Isolated MCGK app with in-memory SQLite (no disk state between tests)
  - async httpx client bound to the test app
  - Helper to register a mock contour
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

# Force test DB to a temp file before importing MCGK
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
os.environ["MCGK_DB_PATH"] = _test_db.name
os.environ["MCGK_HEALTH_INTERVAL"] = "999"  # disable health loop in tests

from mcgk.main import app, registry
from mcgk import persistence


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset in-memory registry and DB between tests."""
    registry.clear()
    # Truncate DB tables
    conn = persistence._connect()
    conn.execute("DELETE FROM contours")
    conn.execute("DELETE FROM request_logs")
    conn.commit()
    conn.close()
    yield
    registry.clear()


@pytest_asyncio.fixture
async def client():
    """Async httpx client wired to the MCGK ASGI app (no real HTTP server needed)."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


SAMPLE_PASSPORT = {
    "name": "echo",
    "address": "http://localhost:9999",
    "description": "A test echo service.",
    "endpoints": [
        {
            "path": "/echo",
            "method": "POST",
            "description": "Echoes the request body.",
            "accepts": {"type": "object"},
            "returns": {"type": "object"},
        }
    ],
}


async def register_contour(client: httpx.AsyncClient, passport: dict | None = None) -> dict:
    """Register a contour and return the response JSON."""
    p = passport or SAMPLE_PASSPORT
    resp = await client.post("/register", json=p)
    return resp.json()
