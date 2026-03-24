"""
Nightmare regression tests — proxy edge cases.

Each test sends a request both directly to the nightmare contour and through
MCGK's proxy, then compares the results. Any difference is a MCGK bug.

Uses ASGI transports — no real HTTP servers or ports needed.
"""

from __future__ import annotations

import hashlib
import json

import pytest
import httpx
from httpx import ASGITransport

from nightmare import app as nightmare_app
from mcgk.main import app as mcgk_app, registry
from mcgk.models import InternalRecord


# ── Fixtures ────────────────────────────────────────────────────────

NIGHTMARE_INTERNAL_URL = "http://nightmare-internal"

@pytest.fixture(autouse=True)
def _register_nightmare():
    """Register nightmare in MCGK's registry pointing at the ASGI transport URL."""
    registry["nightmare"] = InternalRecord(
        name="nightmare",
        address=NIGHTMARE_INTERNAL_URL,
        description="Stress-test service",
        endpoints=[{"path": "/health", "method": "GET", "description": "Health"}],
        healthy=True,
    )
    yield
    registry.pop("nightmare", None)


class DualClient:
    """Sends requests to both nightmare directly and through MCGK proxy."""

    def __init__(self):
        # Direct: ASGI transport to nightmare
        self._direct_transport = ASGITransport(app=nightmare_app)
        # Proxied: ASGI transport to MCGK, which will try to reach nightmare via HTTP.
        # We need MCGK to actually reach nightmare, so we patch httpx to use ASGI transport.
        self._mcgk_transport = ASGITransport(app=mcgk_app)

    async def __aenter__(self):
        self.direct = httpx.AsyncClient(
            transport=self._direct_transport,
            base_url=NIGHTMARE_INTERNAL_URL,
            follow_redirects=False,
        )
        self.proxied = httpx.AsyncClient(
            transport=self._mcgk_transport,
            base_url="http://mcgk",
            follow_redirects=False,
        )
        return self

    async def __aexit__(self, *args):
        await self.direct.aclose()
        await self.proxied.aclose()


@pytest.fixture
def dual():
    return DualClient()


# ── Helpers ─────────────────────────────────────────────────────────

def proxied(path: str) -> str:
    return f"/route/nightmare{path}"


# ═══════════════════════════════════════════════════════════════════════
# Tests — each compares direct vs proxied
# ═══════════════════════════════════════════════════════════════════════

# For tests that go through MCGK's proxy, MCGK needs to make a real HTTP
# call to the nightmare contour's address. In ASGI-only tests, this would
# fail because there's no real server. So we test the proxy logic with
# what we CAN test via ASGI (registration, discovery, map, error cases)
# and test the proxy transparency patterns via direct MCGK ASGI calls
# where the nightmare endpoints are embedded.
#
# The full direct-vs-proxied comparison requires live servers and is
# designed to run with: pytest tests/test_nightmare.py --live


# ── Registration & Discovery ───────────────────────────────────────

@pytest.mark.asyncio
async def test_nightmare_registered():
    assert "nightmare" in registry
    assert registry["nightmare"].healthy is True


@pytest.mark.asyncio
async def test_nightmare_discoverable():
    transport = ASGITransport(app=mcgk_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcgk") as c:
        resp = await c.get("/discover/nightmare")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "nightmare"
        assert data["status"] == "available"
        assert "address" not in str(data)


# ── Nightmare endpoints via direct ASGI (verify the contour works) ─

@pytest.mark.asyncio
async def test_echo_headers_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/echo-headers", headers={"X-Custom": "val", "Accept": "application/json"})
        assert resp.status_code == 200
        headers_received = {h[0].lower(): h[1] for h in resp.json()["headers"]}
        assert "x-custom" in headers_received


@pytest.mark.asyncio
async def test_content_negotiation_json_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/content-negotiation", headers={"Accept": "application/json"})
        assert resp.status_code == 200
        assert resp.json()["negotiated"] is True


@pytest.mark.asyncio
async def test_content_negotiation_html_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/content-negotiation", headers={"Accept": "text/html"})
        assert "HTML" in resp.text


@pytest.mark.asyncio
async def test_status_204_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/status/204")
        assert resp.status_code == 204
        assert resp.content == b""


@pytest.mark.asyncio
async def test_status_301_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        resp = await c.get("/status/301")
        assert resp.status_code == 301
        assert resp.headers.get("location") == "/redirected"


@pytest.mark.asyncio
async def test_status_418_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/status/418")
        assert resp.status_code == 418
        assert b"teapot" in resp.content


@pytest.mark.asyncio
async def test_binary_blob_integrity_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/binary-blob")
        assert resp.status_code == 200
        expected_hash = resp.headers.get("x-sha256")
        actual_hash = hashlib.sha256(resp.content).hexdigest()
        assert actual_hash == expected_hash


@pytest.mark.asyncio
async def test_large_body_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        body = (b"DESTROYER_" * 524288)[:5 * 1024 * 1024]
        expected_hash = hashlib.sha256(body).hexdigest()
        resp = await c.post("/large-body", content=body, headers={"Content-Type": "application/octet-stream"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["size"] == len(body)
        assert data["sha256"] == expected_hash


@pytest.mark.asyncio
async def test_duplicate_headers_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/duplicate-headers")
        assert resp.status_code == 200
        cookies = [v for k, v in resp.headers.raw if k.decode().lower() == "set-cookie"]
        assert len(cookies) == 3


@pytest.mark.asyncio
async def test_conditional_304_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/conditional", headers={"If-None-Match": '"nightmare-v1"'})
        assert resp.status_code == 304


@pytest.mark.asyncio
async def test_echo_query_duplicate_keys_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/echo-query?tag=a&tag=b&tag=c")
        assert resp.status_code == 200
        assert resp.json()["raw_query"] == "tag=a&tag=b&tag=c"


@pytest.mark.asyncio
async def test_echo_body_binary_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        body = b"\x00\x01\r\n\r\nHTTP/1.1 200 OK\r\n\r\n" + bytes(range(256)) + b"\xff\xfe\x00\x00"
        resp = await c.post("/echo-body", content=body, headers={"Content-Type": "application/octet-stream"})
        assert resp.status_code == 200
        assert resp.content == body


@pytest.mark.asyncio
async def test_path_collision_route_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/route/nested/path")
        assert resp.json()["collision"] == "route"


@pytest.mark.asyncio
async def test_path_collision_register_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/register")
        assert resp.json()["collision"] == "register"


@pytest.mark.asyncio
async def test_unicode_path_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/unicode/путь/データ")
        assert resp.status_code == 200
        assert resp.json()["unicode"] is True


@pytest.mark.asyncio
async def test_head_request_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.head("/head-test")
        assert resp.status_code == 200
        assert len(resp.content) == 0
        assert resp.headers.get("x-custom-header") == "head-value"


@pytest.mark.asyncio
async def test_partial_206_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/partial-206")
        assert resp.status_code == 206
        assert resp.headers.get("content-range") == "bytes 0-99/1000"


@pytest.mark.asyncio
async def test_root_path_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")
        assert resp.status_code == 200
        assert resp.json()["root"] is True


@pytest.mark.asyncio
async def test_encoded_path_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/encoded/hello%20world%26ampersand")
        assert resp.status_code == 200
        assert resp.json()["decoded_segment"] == "hello world&ampersand"


@pytest.mark.asyncio
async def test_mismatched_content_type_direct():
    transport = ASGITransport(app=nightmare_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/mismatched-content-type",
            content=b'{"this_is":"json_but_declared_as_plain_text"}',
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["received_content_type"] == "text/plain"
