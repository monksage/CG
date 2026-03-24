"""
Core MCGK logic tests — registration, discovery, system map, health, observability, persistence.
"""

from __future__ import annotations

import pytest
import httpx

from conftest import SAMPLE_PASSPORT, register_contour


# ═══════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_register_success(client: httpx.AsyncClient):
    resp = await client.post("/register", json=SAMPLE_PASSPORT)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "registered"
    assert data["name"] == "echo"


@pytest.mark.asyncio
async def test_register_duplicate_updates(client: httpx.AsyncClient):
    await register_contour(client)
    resp = await client.post("/register", json=SAMPLE_PASSPORT)
    assert resp.json()["status"] == "updated"


@pytest.mark.asyncio
async def test_register_empty_description_rejected(client: httpx.AsyncClient):
    bad = {**SAMPLE_PASSPORT, "description": "  "}
    resp = await client.post("/register", json=bad)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_empty_endpoint_description_rejected(client: httpx.AsyncClient):
    bad = {**SAMPLE_PASSPORT, "endpoints": [{
        "path": "/x", "method": "GET", "description": "", "accepts": None, "returns": None,
    }]}
    resp = await client.post("/register", json=bad)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_no_endpoints_rejected(client: httpx.AsyncClient):
    bad = {**SAMPLE_PASSPORT, "endpoints": []}
    resp = await client.post("/register", json=bad)
    assert resp.status_code == 422  # Pydantic validation: min_length=1


@pytest.mark.asyncio
async def test_register_missing_fields_rejected(client: httpx.AsyncClient):
    resp = await client.post("/register", json={"name": "x"})
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Discovery
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_discover_registered_contour(client: httpx.AsyncClient):
    await register_contour(client)
    resp = await client.get("/discover/echo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "echo"
    assert data["status"] == "available"
    assert "address" not in data
    assert len(data["endpoints"]) == 1


@pytest.mark.asyncio
async def test_discover_not_registered(client: httpx.AsyncClient):
    resp = await client.get("/discover/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_discover_strips_address(client: httpx.AsyncClient):
    await register_contour(client)
    resp = await client.get("/discover/echo")
    data = resp.json()
    # Must not contain any address/port information
    flat = str(data)
    assert "9999" not in flat
    assert "localhost" not in flat


@pytest.mark.asyncio
async def test_discover_unhealthy_contour_still_available(client: httpx.AsyncClient):
    from mcgk.main import registry
    await register_contour(client)
    registry["echo"].healthy = False

    resp = await client.get("/discover/echo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unreachable"
    assert data["name"] == "echo"
    assert len(data["endpoints"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# System Map
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_map_empty(client: httpx.AsyncClient):
    resp = await client.get("/map")
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_map_shows_registered_contours(client: httpx.AsyncClient):
    await register_contour(client)
    resp = await client.get("/map")
    data = resp.json()
    assert "echo" in data
    assert data["echo"]["status"] == "available"
    assert "description" in data["echo"]
    # Must not contain address
    assert "address" not in str(data)


@pytest.mark.asyncio
async def test_map_shows_multiple_contours(client: httpx.AsyncClient):
    await register_contour(client)
    other = {**SAMPLE_PASSPORT, "name": "other", "address": "http://localhost:8888"}
    await register_contour(client, other)
    resp = await client.get("/map")
    data = resp.json()
    assert len(data) == 2
    assert "echo" in data
    assert "other" in data


# ═══════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_empty(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_health_shows_registered_contours(client: httpx.AsyncClient):
    await register_contour(client)
    resp = await client.get("/health")
    data = resp.json()
    assert "echo" in data
    assert data["echo"]["healthy"] is True


# ═══════════════════════════════════════════════════════════════════════
# Routing — basic checks (no real contour behind, expect 502)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_route_not_registered(client: httpx.AsyncClient):
    resp = await client.get("/route/ghost/anything")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_unhealthy_returns_503(client: httpx.AsyncClient):
    from mcgk.main import registry
    await register_contour(client)
    registry["echo"].healthy = False

    resp = await client.get("/route/echo/anything")
    assert resp.status_code == 503
    data = resp.json()
    assert "discovery" in data["detail"]


# ═══════════════════════════════════════════════════════════════════════
# Observability
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_observe_empty(client: httpx.AsyncClient):
    resp = await client.get("/observe")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_observe_per_contour_empty(client: httpx.AsyncClient):
    resp = await client.get("/observe/echo")
    assert resp.json() == []


# ═══════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_persistence_survives_registry_clear(client: httpx.AsyncClient):
    """Simulate restart: register, clear in-memory, reload from DB."""
    from mcgk.main import registry
    from mcgk.persistence import load_all_contours

    await register_contour(client)
    assert "echo" in registry

    registry.clear()
    assert "echo" not in registry

    restored = load_all_contours()
    assert "echo" in restored
    assert restored["echo"].description == SAMPLE_PASSPORT["description"]
    assert restored["echo"].healthy is False  # unknown after load


@pytest.mark.asyncio
async def test_persistence_log_survives(client: httpx.AsyncClient):
    """Request logs are persisted in SQLite."""
    from mcgk.persistence import save_request_log, load_request_logs
    from mcgk.models import RequestLog

    log = RequestLog(source="test", target="echo", target_path="/x", method="GET", status_code=200, duration_ms=10)
    save_request_log(log)

    loaded = load_request_logs()
    assert len(loaded) == 1
    assert loaded[0]["target"] == "echo"
    assert loaded[0]["source"] == "test"
