# Report: Build Minimal CodeGraph Service

## Result
Done with deviations.

## What was built
`CG/services/codegraph/` — 4 files, 342 lines total:
- `db.py` (132) — SQLite: schema init, node CRUD, edge CRUD, graph query, Dunbar-circle context walk, search.
- `main.py` (89) — FastAPI app with all endpoints: `/node`, `/edge`, `/graph`, `/context/{id}`, `/search`.
- `models.py` (78) — Pydantic request/response models.
- `register.py` (43) — Self-registration in MCGK as "codegraph" on startup.

Service registers in MCGK on port 39050, runs on port 39051. All endpoints from the order are implemented.

## Deviations from order
1. **`check_same_thread=False`** added to `sqlite3.connect()`. FastAPI runs sync endpoint functions in a threadpool — without this flag, SQLite raises `ProgrammingError`. Not in the order, but required for the service to function.
2. **Mutable `_state` dict** instead of a global `conn` variable. `uvicorn.run("main:app", ...)` reimports the module, so a plain global set in lifespan is not visible to endpoint functions. Standard Python workaround.
3. **`NO_PROXY='*'` required at runtime.** The environment has an HTTP proxy (`http_proxy=http://127.0.0.1:12334`) that intercepts localhost traffic. Both curl and httpx need proxy bypass. The codegraph code itself uses httpx for MCGK registration, so the proxy env var affects it. Not a code issue — an environment issue.

## Verification
1. Start MCGK — **pass**
2. Start CodeGraph — **pass**
3. Check registration (`/map`) — **pass** ("codegraph", status "available")
4. Create node (`validate_jwt`) — **pass**
5. Read node back — **pass**
6. Second node + edge + `/context/validate_jwt` — **pass** (depth 0: full code+specs, depth 1: spec_summary+contract)
7. Delete node with incoming edges — **pass** (409, blocked)
8. `/graph` — **pass** (ids + edges only, no code/specs)
9. Route through MCGK (`/route/codegraph/node/validate_jwt`) — **pass**

## Open issues
1. **Proxy environment.** `http_proxy` is set system-wide and intercepts localhost. CodeGraph's `register.py` uses httpx which respects proxy env vars by default. If MCGK registration fails in future runs, check that `NO_PROXY=*` or `NO_PROXY=localhost,127.0.0.1` is set. Could also add `trust_env=False` to the httpx client, but that changes behavior beyond scope.
2. **MCGK config default port.** `CG/src/mcgk/config.py` still defaults to port 6245. The order says ports were updated to 39050 range but the constraint forbids modifying MCGK files. MCGK must be started with `MCGK_PORT=39050` env var. Not a codegraph issue — noting for the sergeant.
