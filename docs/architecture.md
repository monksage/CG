# MCGK Architecture

## Overview

MCGK is a single-process Python server (FastAPI + uvicorn) that sits between all contours in a system. It has three responsibilities:

1. **Registry** — know which contours exist and how to reach them
2. **Proxy** — route requests between contours by name
3. **Discovery** — let contours learn each other's interfaces without exposing locations

```
┌─────────┐     ┌──────┐     ┌─────────┐
│ Contour A│────>│ MCGK │────>│ Contour B│
│          │<────│      │<────│          │
└─────────┘     └──────┘     └─────────┘
                  │  ▲
                  v  │
               ┌────────┐
               │ SQLite  │
               └────────┘
```

## Data flow

### Registration

1. Contour starts up, knows only MCGK's address
2. Contour POSTs its passport to `/register`
3. MCGK validates the passport, stores it in-memory + SQLite
4. Contour is now routable

### Discovery

1. Caller GETs `/discover/{name}` or `/map`
2. MCGK returns the passport: endpoint descriptions, request/response schemas
3. **Address is never returned** — the caller only learns *what* the contour does, not *where* it is
4. Caller adapts (melts) its request to fit the target's schema

### Routing

1. Caller POSTs/GETs to `/route/{name}/{path}?query=params`
2. MCGK looks up the name in the registry
3. MCGK forwards the request to the contour's internal address, preserving:
   - All headers (including duplicates like multiple Cookie headers)
   - Query string (verbatim)
   - Request body (binary-safe)
   - HTTP method
4. MCGK returns the response to the caller, preserving:
   - Status code (including 204, 206, 301, 304, 418, etc.)
   - All headers (including duplicates like multiple Set-Cookie headers)
   - Response body (binary-safe, streaming-safe)
5. If the response is streaming (SSE, NDJSON, chunked), MCGK streams it through in real-time

### Health monitoring

A background task pings `GET /health` on every registered contour at a configurable interval. Unhealthy contours are marked but not deleted. Requests to unhealthy contours return 503 with a pointer to discovery. Recovery is detected automatically.

## Persistence

SQLite (WAL mode) stores two tables:

- **contours** — name, address, description, endpoints JSON, registration timestamp
- **request_logs** — timestamp, source, target, path, method, status, error, duration

On startup, MCGK loads all contours from SQLite with `healthy=false`. Health checks confirm liveness. This means passports survive restarts — a contour can be discovered even before it comes back online.

## Isolation model

Information MCGK keeps internal (never in any external response):
- Contour addresses and ports
- Health check timestamps and internals
- SQLite paths and DB structure

Information MCGK exposes to contours:
- Contour names and descriptions
- Endpoint path, method, description, accepts/returns schemas
- Availability status (`available` / `unreachable`)
- Proxied request/response data (pass-through, not interpreted)

## Error handling

MCGK intervenes only for infrastructure-level failures:

| Situation | Response |
|---|---|
| Target not registered | 404 |
| Target unhealthy | 503 + discovery pointer |
| Target unreachable | 502 + discovery pointer |
| Target timeout | 504 + discovery pointer |
| Target returns any error (4xx, 5xx) | **Passed through as-is** |

Contour-level errors are the caller's responsibility to interpret using the passport.
