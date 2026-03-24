"""
MCGK — Melting Contract GateKeeper
====================================
A proxy server that acts as the sole communication hub between independent
services (contours). No contour knows where any other contour lives.

Endpoints:
  POST /register              – Register a contour with a validated passport
  ANY  /route/{name}/{path}   – Proxy any request to a contour by name
  GET  /discover/{name}       – Return a contour's external passport (no address/port)
  GET  /map                   – System map: contour names + status
  GET  /observe               – All request logs (persistent)
  GET  /observe/{name}        – Request logs for one contour
  GET  /health                – Health summary of all contours

Configuration via environment variables — see config.py for full list.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from . import __version__
from .config import HEALTH_INTERVAL, PROXY_TIMEOUT, STREAM_TIMEOUT, TRUST_ENV
from .models import InternalRecord, RegistrationRequest, RequestLog
from .persistence import load_all_contours, load_request_logs, save_contour, save_request_log

# ── State ────────────────────────────────────────────────────────────

registry: dict[str, InternalRecord] = {}

# Headers that must not be forwarded (hop-by-hop or proxy-internal)
_HOP_BY_HOP = frozenset({
    "host", "connection", "keep-alive", "transfer-encoding",
    "te", "trailer", "upgrade", "proxy-authorization",
    "proxy-authenticate", "x-contour-source",
})

# Content types that indicate a streaming response
_STREAMING_TYPES = ("text/event-stream", "application/x-ndjson", "application/stream+json")


# ── Health-check background task ─────────────────────────────────────

async def _health_loop() -> None:
    """Periodically ping every registered contour."""
    async with httpx.AsyncClient(timeout=3, trust_env=TRUST_ENV) as client:
        while True:
            await asyncio.sleep(HEALTH_INTERVAL)
            for name, record in list(registry.items()):
                try:
                    r = await client.get(f"{record.address}/health")
                    record.healthy = r.status_code < 500
                except Exception:
                    record.healthy = False
                record.last_health_check = time.time()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Restore registry from SQLite, start health checks."""
    registry.update(load_all_contours())
    task = asyncio.create_task(_health_loop())
    yield
    task.cancel()


app = FastAPI(
    title="MCGK — Melting Contract GateKeeper",
    description=(
        "Proxy server that acts as the sole communication hub between independent "
        "services (contours). Contours register with a passport describing their "
        "interface. Other contours discover passports at runtime and adapt (melt) "
        "their requests to fit. MCGK never exposes addresses — routing is by name only."
    ),
    version=__version__,
    lifespan=lifespan,
)


# ── 1. Registration ─────────────────────────────────────────────────

@app.post(
    "/register",
    summary="Register a contour",
    description=(
        "Register a contour with MCGK. The request must include a complete passport: "
        "name, address, description, and at least one endpoint with a description. "
        "Duplicate names are updated in place. Routes are added at runtime."
    ),
)
async def register(req: RegistrationRequest):
    if not req.description.strip():
        raise HTTPException(400, "Passport must include a non-empty description.")
    for ep in req.endpoints:
        if not ep.description.strip():
            raise HTTPException(400, f"Endpoint {ep.path} must include a description.")

    record = InternalRecord(
        name=req.name,
        address=req.address,
        description=req.description,
        endpoints=req.endpoints,
        healthy=True,
        registered_at=time.time(),
    )

    is_update = req.name in registry
    registry[req.name] = record
    save_contour(record)

    return {"status": "updated" if is_update else "registered", "name": req.name}


# ── 2. Routing ───────────────────────────────────────────────────────

@app.api_route(
    "/route/{contour_name}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    summary="Route a request to a contour",
    description=(
        "Transparent proxy to a contour by name. Forwards query params, all safe "
        "headers (preserving duplicates), binary bodies, and any content-type. "
        "Streaming responses (SSE, NDJSON, chunked) are streamed through in real-time. "
        "Contour errors (4xx, 5xx) pass through as-is — MCGK only intervenes for "
        "infrastructure failures (not registered, unreachable, timeout)."
    ),
)
async def route(contour_name: str, path: str, request: Request):
    record = registry.get(contour_name)
    if record is None:
        raise HTTPException(404, f"Contour '{contour_name}' is not registered.")
    if not record.healthy:
        raise HTTPException(503, {
            "error": f"Contour '{contour_name}' is currently unhealthy.",
            "discovery": f"Passport still available at /discover/{contour_name}",
        })

    # Build target URL preserving query string
    target_url = f"{record.address}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()
    source = request.headers.get("x-contour-source", "unknown")

    # Forward all headers except hop-by-hop — preserve duplicates
    fwd_headers = [
        (k.decode("latin-1"), v.decode("latin-1"))
        for k, v in request.headers.raw
        if k.decode("latin-1").lower() not in _HOP_BY_HOP
    ]

    log = RequestLog(
        source=source,
        target=contour_name,
        target_path=f"/{path}" + (f"?{request.url.query}" if request.url.query else ""),
        method=request.method,
    )
    t0 = time.time()

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(PROXY_TIMEOUT, read=STREAM_TIMEOUT),
        trust_env=TRUST_ENV,
    )

    try:
        req_obj = client.build_request(
            method=request.method,
            url=target_url,
            content=body,
            headers=fwd_headers,
        )
        resp = await client.send(req_obj, stream=True)

        log.status_code = resp.status_code
        log.duration_ms = round((time.time() - t0) * 1000, 2)
        save_request_log(log)

        # Preserve duplicate response headers
        resp_headers_list = [
            (k.decode("latin-1") if isinstance(k, bytes) else k,
             v.decode("latin-1") if isinstance(v, bytes) else v)
            for k, v in resp.headers.raw
            if (k.decode("latin-1") if isinstance(k, bytes) else k).lower() not in _HOP_BY_HOP
        ]

        content_type = resp.headers.get("content-type", "application/octet-stream")
        is_streaming = (
            any(st in content_type for st in _STREAMING_TYPES)
            or "chunked" in resp.headers.get("transfer-encoding", "")
        )

        if is_streaming:
            async def stream_generator():
                try:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                finally:
                    await resp.aclose()
                    await client.aclose()

            sr = StreamingResponse(stream_generator(), status_code=resp.status_code)
            for hk, hv in resp_headers_list:
                sr.headers.append(hk, hv)
            return sr
        else:
            content = await resp.aread()
            await resp.aclose()
            await client.aclose()
            r = Response(content=content, status_code=resp.status_code)
            for hk, hv in resp_headers_list:
                r.headers.append(hk, hv)
            return r

    except httpx.ConnectError:
        await client.aclose()
        record.healthy = False
        log.error = "connection_refused"
        log.duration_ms = round((time.time() - t0) * 1000, 2)
        save_request_log(log)
        raise HTTPException(502, {
            "error": f"Contour '{contour_name}' is unreachable.",
            "discovery": f"Passport still available at /discover/{contour_name}",
        })

    except httpx.TimeoutException:
        await client.aclose()
        log.error = "timeout"
        log.duration_ms = round((time.time() - t0) * 1000, 2)
        save_request_log(log)
        raise HTTPException(504, {
            "error": f"Contour '{contour_name}' timed out.",
            "discovery": f"Passport still available at /discover/{contour_name}",
        })


# ── 3. Melting Discovery ────────────────────────────────────────────

@app.get(
    "/discover/{contour_name}",
    summary="Discover a contour's passport",
    description=(
        "Return the external passport for a contour — endpoint descriptions, "
        "request/response schemas, and availability status. No address or port is "
        "ever exposed. Works even if the contour is currently unreachable."
    ),
)
async def discover(contour_name: str):
    record = registry.get(contour_name)
    if record is None:
        raise HTTPException(404, f"Contour '{contour_name}' is not registered.")

    passport = record.to_external().model_dump()
    passport["status"] = "available" if record.healthy else "unreachable"
    return passport


# ── 4. System Map ───────────────────────────────────────────────────

@app.get(
    "/map",
    summary="System map",
    description=(
        "Every registered contour's name, description, and availability status. "
        "Use /discover/{name} to get the full passport for a specific contour."
    ),
)
async def system_map():
    return {
        name: {
            "description": rec.description,
            "status": "available" if rec.healthy else "unreachable",
        }
        for name, rec in registry.items()
    }


# ── 5. Observability ────────────────────────────────────────────────

@app.get(
    "/observe",
    summary="All request logs",
    description="All proxied-request logs, newest first. Persisted in SQLite.",
)
async def observe_all():
    return load_request_logs()


@app.get(
    "/observe/{contour_name}",
    summary="Request logs for a contour",
    description="Request logs involving a specific contour (as routing target).",
)
async def observe_contour(contour_name: str):
    return load_request_logs(target=contour_name)


# ── 6. Health ────────────────────────────────────────────────────────

@app.get(
    "/health",
    summary="Health summary",
    description="Health status and last check timestamp for every registered contour.",
)
async def health():
    return {
        name: {
            "healthy": rec.healthy,
            "last_check": rec.last_health_check,
        }
        for name, rec in registry.items()
    }


# ── Run ──────────────────────────────────────────────────────────────

def main():
    """Entry point for running MCGK directly."""
    import uvicorn
    from .config import HOST, LOG_LEVEL, PORT
    uvicorn.run("mcgk.main:app", host=HOST, port=PORT, log_level=LOG_LEVEL)


if __name__ == "__main__":
    main()
