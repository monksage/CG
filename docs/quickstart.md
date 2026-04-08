# Quick-Start Guide: Integrating a New Contour with MCGK

This guide shows how to build a contour (service) that registers with MCGK, becomes discoverable, and can be reached by other contours.

## Prerequisites

- MCGK is running (default: `http://localhost:39050`)
- Your contour is an HTTP server (any language/framework)

## Step 1: Build your service

Your service needs:
- At least one endpoint that does something useful
- A `GET /health` endpoint returning HTTP 200 (MCGK uses this for health checks)

Example (Python/FastAPI):

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/greet")
def greet(data: dict):
    name = data.get("name", "world")
    return {"greeting": f"Hello, {name}!"}
```

## Step 2: Register with MCGK

On startup (or manually), POST your passport to MCGK:

```bash
curl -X POST http://localhost:39050/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "greeter",
    "address": "http://localhost:9001",
    "description": "Greeting service. Says hello to people.",
    "endpoints": [
      {
        "path": "/greet",
        "method": "POST",
        "description": "Generate a personalized greeting.",
        "accepts": {
          "type": "object",
          "properties": {"name": {"type": "string"}},
          "required": ["name"]
        },
        "returns": {
          "type": "object",
          "properties": {"greeting": {"type": "string"}}
        }
      }
    ]
  }'
```

Response: `{"status": "registered", "name": "greeter"}`

## Step 3: Verify discovery

```bash
curl http://localhost:39050/discover/greeter
```

Your passport is now available to anyone who asks. Note: no address in the response.

## Step 4: Call your service through MCGK

Other contours (or external clients) call you through MCGK:

```bash
curl -X POST http://localhost:39050/route/greeter/greet \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice"}'
```

Response: `{"greeting": "Hello, Alice!"}`

## Step 5: Discover and call other contours

To interact with another contour:

```bash
# 1. See what's available
curl http://localhost:39050/map

# 2. Learn a specific contour's interface
curl http://localhost:39050/discover/other-service

# 3. Adapt your request to match its schema, then route through MCGK
curl -X POST http://localhost:39050/route/other-service/endpoint \
  -H "Content-Type: application/json" \
  -d '{"field": "value"}'
```

## Tips

- **Include the `X-Contour-Source` header** in your requests so MCGK can track them in observability logs:
  ```
  X-Contour-Source: greeter
  ```

- **Always check discovery before calling** — the target's interface may have changed since you last checked.

- **Handle errors yourself** — if a contour returns 400 or 422, the passport tells you what it expects. Adapt your request.

- **Your passport should be detailed** — the more information in `accepts`/`returns`, the easier it is for callers to integrate without guessing.

## Programmatic registration (Python example)

```python
import httpx

MCGK = "http://localhost:39050"

passport = {
    "name": "greeter",
    "address": "http://localhost:9001",
    "description": "Greeting service.",
    "endpoints": [
        {
            "path": "/greet",
            "method": "POST",
            "description": "Generate a greeting.",
            "accepts": {"type": "object", "properties": {"name": {"type": "string"}}},
            "returns": {"type": "object", "properties": {"greeting": {"type": "string"}}},
        }
    ],
}

# Register on startup
resp = httpx.post(f"{MCGK}/register", json=passport)
print(resp.json())

# Discover another contour
passport = httpx.get(f"{MCGK}/discover/other-service").json()
print(passport["endpoints"])

# Route a request
result = httpx.post(
    f"{MCGK}/route/other-service/endpoint",
    json={"input": "data"},
    headers={"X-Contour-Source": "greeter"},
)
print(result.json())
```
