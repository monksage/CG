# Build Minimal CodeGraph Service

## Role

You are building the first backend service for Contour Graph — the CodeGraph API. This is the foundation everything else depends on.

## Objective

Build a minimal CodeGraph service: a FastAPI application with SQLite storage that manages a graph of code nodes and edges. Register it in the running MCGK gate as "codegraph".

This is an experiment. The goal is to verify that agents can work with code through a graph API instead of files. Build the minimum needed to test that hypothesis — nothing more.

## What to build

### Location

Create the service at `CG/services/codegraph/`. Structure:

```
CG/services/codegraph/
    main.py          # FastAPI app, entry point
    models.py        # Pydantic models
    db.py            # SQLite operations
    register.py      # Self-registration in MCGK on startup
```

### Database schema

SQLite, WAL mode. Two tables for now.

```sql
CREATE TABLE nodes (
    id          TEXT PRIMARY KEY,       -- human-readable: "validate_jwt", "calc_r2"
    code        TEXT NOT NULL,          -- clean code, no imports
    language    TEXT NOT NULL,          -- "python", "typescript", "rust"
    kind        TEXT NOT NULL,          -- "contour" | "micro" | "config"
    status      TEXT DEFAULT 'draft',   -- "draft" | "golden" | "deprecated"
    version     INTEGER DEFAULT 1,

    -- contract
    accepts     TEXT DEFAULT '{}',      -- JSON: input parameters
    returns     TEXT DEFAULT '{}',      -- JSON: return value

    -- dependencies
    imports     TEXT DEFAULT '[]',      -- JSON: ["from datetime import datetime", ...]
    tags        TEXT DEFAULT '[]',      -- JSON: ["auth", "api"]

    -- specs (four Dunbar levels)
    spec_ticket TEXT DEFAULT '',        -- 10-15 lines: what it does, contract, edge cases
    spec_summary TEXT DEFAULT '',       -- full description: inputs, outputs, dependencies, decisions
    -- spec_name = the node id itself (human-readable name IS the name-level spec)
    -- spec_as_is = code + all specs above (assembled on read, not stored)

    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE edges (
    source_id   TEXT NOT NULL REFERENCES nodes(id),
    target_id   TEXT NOT NULL REFERENCES nodes(id),
    edge_type   TEXT NOT NULL,          -- "calls" | "uses" | "extends" | "tests"
    PRIMARY KEY (source_id, target_id, edge_type)
);
```

No versions table. No products table. No tags table. Those come later.

### API endpoints

**CRUD:**

```
POST   /node              -- create node (id, code, language, kind, specs, contract)
GET    /node/{id}         -- full node (code + specs + contract + edges)
PUT    /node/{id}         -- update node (creates no version history yet — just overwrites)
DELETE /node/{id}         -- delete only if no incoming edges
POST   /edge              -- add edge {source_id, target_id, edge_type}
DELETE /edge              -- remove edge {source_id, target_id, edge_type}
GET    /graph             -- all node ids + all edges (no code, no specs)
```

**Context (Dunbar circles):**

```
GET /context/{id}         -- returns a context package:
                          --   target node: full code + all specs (as_is)
                          --   direct neighbors (depth 1): spec_summary + accepts/returns
                          --   depth 2 neighbors: spec_ticket
                          --   everything else in graph: node id only (the name IS the spec)
```

The `/context/{id}` endpoint walks the graph from the target node outward. Depth is measured in edge hops. A node appears at the closest depth where it's found (no duplicates).

**Search:**

```
GET /search?query={text}  -- search by node id and spec_ticket (simple LIKE match is fine)
```

### MCGK registration

On startup, the service registers itself with MCGK at the configured address. Use a passport describing all endpoints above with their request/response schemas. If MCGK is not reachable at startup, log a warning and continue — registration can be retried manually.

Read `CG/src/mcgk/models.py` to understand the passport format. The registration call is `POST /register` to MCGK with an `ExternalPassport` payload containing the service address.

### Configuration

Environment variables:

```
CODEGRAPH_PORT=39051
CODEGRAPH_HOST=0.0.0.0
CODEGRAPH_DB_PATH=codegraph.db
MCGK_URL=http://localhost:39050
```

Port range for this project: 39050-39080. MCGK runs on 39050. CodeGraph on 39051. Future services take the next available port in range.

## Constraints

- **No versions table.** Versioning is a later experiment.
- **No products table.** Multi-product is a later experiment.
- **No /similar endpoint.** Reuse search is a later experiment.
- **No tags suggest/fuzzy match.** Tags are stored as JSON array on the node, that's it for now.
- **No authentication.** Everything runs locally.
- **No streaming.** Simple request/response.
- **Do not modify anything in `CG/src/mcgk/`.** MCGK is a separate service, already working.
- Python 3.11+, FastAPI, httpx (for MCGK registration), SQLite. Same stack as MCGK.
- Keep it under 400 lines total across all files. This is a minimal service.

## Verification

After building, verify with these steps:

1. Start MCGK: `cd CG && python -m mcgk.main`
2. Start CodeGraph: `cd CG/services/codegraph && python main.py`
3. Check registration: `curl http://localhost:39050/map` — should show "codegraph" as registered.
4. Create a node:
```bash
curl -X POST http://localhost:39051/node -H "Content-Type: application/json" -d '{
  "id": "validate_jwt",
  "code": "def validate_jwt(token: str) -> dict:\n    if not token:\n        raise ValueError(\"empty token\")\n    payload = decode(token)\n    if payload[\"exp\"] < now():\n        raise ExpiredError()\n    return payload",
  "language": "python",
  "kind": "contour",
  "accepts": "{\"token\": \"str\"}",
  "returns": "{\"payload\": \"dict\"}",
  "tags": ["auth", "api"],
  "spec_ticket": "Validates a JWT token. Checks presence, decodes, verifies expiration. Raises ValueError on empty, ExpiredError on expired. Returns decoded payload dict.",
  "spec_summary": "JWT validation contour. Accepts a raw token string, performs three checks: non-empty, decodable, not expired. Each check is a decision point. Dependencies: decode() from jwt lib, now() for time. Returns the decoded payload as dict. Edge cases: malformed tokens raise DecodeError from the jwt lib, not caught here — caller handles."
}'
```
5. Read it back: `curl http://localhost:39051/node/validate_jwt`
6. Create a second node and an edge, then test `/context/validate_jwt` — verify Dunbar circle assembly.
7. Test deletion constraint: try to delete a node that has incoming edges — should fail.
8. Test graph endpoint: `curl http://localhost:39051/graph` — should return ids and edges only.
9. Test routing through MCGK: `curl http://localhost:39050/route/codegraph/node/validate_jwt` — should return the node.

## Subagent guidance

This is small enough to do yourself. If you find yourself writing boilerplate (Pydantic models for all endpoints), consider spawning a soldier for that while you focus on the database layer and context assembly logic. The `/context/{id}` endpoint is the most important piece — the Dunbar circle graph walk. Do that yourself.
