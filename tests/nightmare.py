"""
Nightmare Service — stress-test contour for MCGK proxy regression tests.

A FastAPI server with legitimate but proxy-hostile endpoints. Each endpoint
targets a specific weakness commonly found in naive HTTP proxies.

Used by test_nightmare.py. Can also be run standalone:
    python -m tests.nightmare
"""

from __future__ import annotations

import asyncio
import hashlib
import struct
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

app = FastAPI(title="Nightmare Service")


@app.get("/health")
async def health():
    return {"status": "alive", "service": "nightmare"}


# ── Header echo ─────────────────────────────────────────────────────

@app.get("/echo-headers")
async def echo_headers(request: Request):
    """Return every header received as [key, value] pairs to preserve duplicates."""
    headers_list = [[k.decode(), v.decode()] for k, v in request.headers.raw]
    return {"headers": headers_list}


# ── Content negotiation ─────────────────────────────────────────────

@app.get("/content-negotiation")
async def content_negotiation(request: Request):
    accept = request.headers.get("accept", "application/json")
    if "text/html" in accept:
        return Response(content="<h1>Hello HTML</h1>", media_type="text/html")
    elif "text/plain" in accept:
        return Response(content="Hello Plain Text", media_type="text/plain")
    elif "application/octet-stream" in accept:
        return Response(content=b"\x00\x01\x02\x03\xff\xfe\xfd", media_type="application/octet-stream")
    else:
        return {"message": "Hello JSON", "negotiated": True}


# ── Arbitrary status codes ──────────────────────────────────────────

@app.get("/status/{code}")
async def status_code(code: int):
    if code == 204:
        return Response(status_code=204)
    elif code == 301:
        return Response(status_code=301, headers={"Location": "/redirected"})
    elif code == 304:
        return Response(status_code=304, headers={"ETag": '"abc123"'})
    elif code == 418:
        return Response(content=b"I'm a teapot", status_code=418, media_type="text/plain")
    else:
        return Response(content=f"Status {code}".encode(), status_code=code, media_type="text/plain")


# ── Binary blob ─────────────────────────────────────────────────────

@app.get("/binary-blob")
async def binary_blob():
    data = bytearray()
    data.extend(b"\xef\xbb\xbf")  # UTF-8 BOM
    data.extend(b"\x00\x00\x00")  # Null bytes
    data.extend(b"\r\n\r\n")      # CRLF (looks like HTTP line endings)
    data.extend(bytes(range(0x80, 0x100)))  # High bytes (invalid UTF-8)
    data.extend(b"0\r\n\r\n")     # Looks like chunked transfer markers
    data.extend(b"\xff" * 256)
    for i in range(10):
        data.extend(struct.pack("<d", i * 3.14159))
    return Response(
        content=bytes(data),
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(data)), "X-SHA256": hashlib.sha256(bytes(data)).hexdigest()},
    )


# ── Chunked streaming (non-SSE) ────────────────────────────────────

@app.get("/chunked-stream")
async def chunked_stream():
    async def generate():
        for i in range(20):
            yield f"chunk-{i:04d}|".encode()
            await asyncio.sleep(0.01)
    return StreamingResponse(generate(), media_type="application/octet-stream")


# ── NDJSON stream ───────────────────────────────────────────────────

@app.get("/ndjson-stream")
async def ndjson_stream():
    async def generate():
        for i in range(10):
            yield f'{{"index":{i},"ts":{time.time()}}}\n'.encode()
            await asyncio.sleep(0.05)
    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ── Large body echo ────────────────────────────────────────────────

@app.post("/large-body")
async def large_body(request: Request):
    body = await request.body()
    return {"size": len(body), "sha256": hashlib.sha256(body).hexdigest()}


# ── Multipart mixed ────────────────────────────────────────────────

@app.post("/multipart-mixed")
async def multipart_mixed(request: Request):
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    return {
        "content_type_received": content_type,
        "body_size": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
    }


# ── Slow SSE stream ────────────────────────────────────────────────

@app.get("/slow-stream")
async def slow_stream():
    async def generate():
        for i in range(5):
            yield f"data: event-{i}\n\n".encode()
            await asyncio.sleep(0.1)
        yield b"data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Conditional GET (304) ──────────────────────────────────────────

@app.get("/conditional")
async def conditional(request: Request):
    etag = '"nightmare-v1"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(content=b"Full content here", status_code=200, media_type="text/plain", headers={"ETag": etag})


# ── Duplicate response headers ─────────────────────────────────────

@app.get("/duplicate-headers")
async def duplicate_headers():
    response = Response(content=b'{"ok":true}', media_type="application/json")
    response.headers.append("Set-Cookie", "session=abc123; Path=/; HttpOnly")
    response.headers.append("Set-Cookie", "theme=dark; Path=/")
    response.headers.append("Set-Cookie", "lang=en; Path=/")
    response.headers.append("X-Custom", "value1")
    response.headers.append("X-Custom", "value2")
    return response


# ── 204 No Content ────────────────────────────────────────────────

@app.delete("/empty-204")
async def empty_204():
    return Response(status_code=204)


# ── Redirect ──────────────────────────────────────────────────────

@app.get("/redirect")
async def redirect():
    return Response(status_code=301, headers={"Location": "/final-destination"})


# ── Query string echo ─────────────────────────────────────────────

@app.get("/echo-query")
async def echo_query(request: Request):
    return {"raw_query": str(request.url.query), "url": str(request.url)}


# ── Body echo (byte-for-byte) ─────────────────────────────────────

@app.post("/echo-body")
async def echo_body(request: Request):
    body = await request.body()
    return Response(
        content=body,
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(body)), "X-Body-SHA256": hashlib.sha256(body).hexdigest()},
    )


# ── Path collisions ──────────────────────────────────────────────

@app.get("/route/nested/path")
async def route_collision():
    return {"collision": "route", "reached": True}


@app.get("/register")
async def register_collision():
    return {"collision": "register", "reached": True}


# ── Unicode path ─────────────────────────────────────────────────

@app.get("/unicode/путь/データ")
async def unicode_path():
    return {"unicode": True, "path": "/unicode/путь/データ"}


# ── HEAD request ─────────────────────────────────────────────────

@app.head("/head-test")
async def head_test_head():
    return Response(status_code=200, headers={
        "Content-Type": "application/json", "Content-Length": "42", "X-Custom-Header": "head-value",
    })

@app.get("/head-test")
async def head_test_get():
    body = b'{"method":"GET","content_length_matches":true}'
    return Response(content=body, status_code=200, media_type="application/json", headers={
        "Content-Length": str(len(body)), "X-Custom-Header": "head-value",
    })


# ── 206 Partial Content ─────────────────────────────────────────

@app.get("/partial-206")
async def partial_206():
    chunk = b"A" * 100
    return Response(content=chunk, status_code=206, media_type="application/octet-stream", headers={
        "Content-Range": "bytes 0-99/1000", "Content-Length": "100",
    })


# ── Mismatched content-type ─────────────────────────────────────

@app.post("/mismatched-content-type")
async def mismatched_content_type(request: Request):
    body = await request.body()
    ct = request.headers.get("content-type", "not-set")
    return {"received_content_type": ct, "body_text": body.decode("utf-8", errors="replace"), "body_size": len(body)}


# ── Encoded path ────────────────────────────────────────────────

@app.get("/encoded/{segment}")
async def encoded_path(segment: str, request: Request):
    return {"decoded_segment": segment, "raw_path": str(request.url.path)}


# ── Root path ───────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"root": True, "path": "/"}


# ── Standalone run ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("nightmare:app", host="0.0.0.0", port=6660, log_level="warning")
