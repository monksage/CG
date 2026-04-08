# Add Version System to CodeGraph

## Role

You are extending the CodeGraph service with a version system for nodes. This changes how nodes are created, updated, and queried.

## Objective

Add a `versions` table to CodeGraph. Every node mutation creates a version. Nodes have a lifecycle: draft → golden → rejected → deprecated. Migrate all existing nodes (66) to version 1 as golden. Replace the current PUT-overwrites-node behavior with explicit versioned actions.

## What to change

### Location

Modify existing files in `CG/services/codegraph/`: `db.py`, `main.py`, `models.py`. No new files.

### Database: add versions table

```sql
CREATE TABLE versions (
    node_id     TEXT NOT NULL REFERENCES nodes(id),
    version     INTEGER NOT NULL,
    code        TEXT NOT NULL,
    spec_ticket TEXT DEFAULT '',
    spec_summary TEXT DEFAULT '',
    accepts     TEXT DEFAULT '{}',
    returns     TEXT DEFAULT '{}',
    imports     TEXT DEFAULT '[]',
    task_id     TEXT DEFAULT '',
    status      TEXT DEFAULT 'draft',   -- "draft" | "golden" | "rejected" | "deprecated"
    created_at  REAL NOT NULL,
    PRIMARY KEY (node_id, version)
);
```

### Migration

On startup, for every existing node in `nodes` table that has no entry in `versions`: create a version 1 record copying code, spec_ticket, spec_summary, accepts, returns, imports from the node. Set status = "golden", task_id = "migration". This is idempotent — running it twice doesn't create duplicates.

### New API endpoints

```
POST /node/{id}/version          -- create new draft version (body: code, specs, contracts, task_id)
POST /node/{id}/promote          -- promote latest draft → golden. Previous golden → deprecated.
POST /node/{id}/reject           -- latest draft → rejected
GET  /node/{id}/versions         -- list all versions of a node
GET  /node/{id}/version/{n}      -- get specific version
```

### Changed API endpoints

```
GET  /node/{id}                  -- returns the golden version. If no golden, returns latest draft.
POST /node                       -- creates node + version 1 as draft (not golden).
```

### Removed

```
PUT  /node/{id}                  -- removed. Use POST /node/{id}/version instead.
```

### Lifecycle rules

- `POST /node` creates a node entry + version 1 with status "draft".
- `POST /node/{id}/version` creates a new version with status "draft". Version number = max existing + 1.
- `POST /node/{id}/promote` sets latest draft to "golden". Any existing golden version of that node becomes "deprecated". Returns 409 if no draft version exists.
- `POST /node/{id}/reject` sets latest draft to "rejected". Returns 409 if no draft version exists.
- `GET /node/{id}` returns the node from nodes table (which is the cached active version). The `version` and `status` fields must be included in the response. If node has only rejected versions, returns the node with status "rejected".
- **Nodes table keeps ALL existing columns** — id, language, kind, tags, code, spec_ticket, spec_summary, accepts, returns, imports, status, created_at, updated_at. Nothing is removed. Nodes table acts as a **cache of the active version**. Versions table is the source of truth.
- On promote: copy the promoted version's code/specs/contracts/status into the nodes row. On reject: if no golden exists, copy the rejected version's fields with status "rejected" into nodes row.
- This means all existing read paths (GET /node, GET /context, GET /search) work unchanged — they read from nodes table. Versions table is the audit log + draft workspace.

### Context endpoint

`GET /context/{id}` should use golden versions for all nodes. If a node has no golden version, use latest draft. No changes to the Dunbar circle logic — only the version selection layer.

### Build script

Update `CG/services/codegraph/build.py` to use golden versions. `GET /node/{id}` already returns golden by default, so build.py may need no changes — verify.

## Constraints

- Do not break existing edges. Edges reference node ids, not versions. This doesn't change.
- Do not break /graph endpoint. It returns node ids + edges, not version data.
- Do not break /search endpoint. Search should query the active version (golden or latest draft).
- Use `NO_PROXY=localhost,127.0.0.1` for all HTTP requests.
- Keep the same stack: Python 3.11+, FastAPI, SQLite.
- MCGK runs on port 39050, CodeGraph on port 39051.

## Verification

1. Start services. Check that migration ran: `GET /node/process_signal` should return version 1, status "golden".
2. `GET /node/process_signal/versions` should return one entry (version 1, golden, task_id "migration").
3. Create a new node:
```bash
curl -X POST http://localhost:39051/node -H "Content-Type: application/json" -d '{
  "id": "test_versioning",
  "code": "def test_v1(): return 1",
  "language": "python",
  "kind": "contour",
  "spec_ticket": "Version 1 of test node."
}'
```
Should return version 1, status "draft".

4. `GET /node/test_versioning` should return the draft (no golden exists yet).

5. Promote it:
```bash
curl -X POST http://localhost:39051/node/test_versioning/promote
```
Should return version 1, status "golden".

6. Create version 2:
```bash
curl -X POST http://localhost:39051/node/test_versioning/version -H "Content-Type: application/json" -d '{
  "code": "def test_v2(): return 2",
  "spec_ticket": "Version 2, improved."
}'
```
Should return version 2, status "draft".

7. `GET /node/test_versioning` should still return version 1 (golden), not version 2 (draft).

8. Promote version 2:
```bash
curl -X POST http://localhost:39051/node/test_versioning/promote
```
Version 2 → golden, version 1 → deprecated.

9. `GET /node/test_versioning/versions` should show: v1 deprecated, v2 golden.

10. `GET /context/process_signal` should still work — uses golden versions.

11. Verify PUT /node/{id} is gone — should return 405 Method Not Allowed or 404.

12. Test routing through MCGK: `curl http://localhost:39050/route/codegraph/node/process_signal` should return golden version.

## Report

Write to `corporal_reports/add_versions_to_codegraph_report.md`.

## Clarified decisions

These were raised during review and resolved:

1. **Nodes as cache, not moved.** Code/specs/contracts stay in both tables. Versions = source of truth. Nodes = cache of active version, synced on promote/reject. This avoids rewriting all read paths.
2. **Rejected-only nodes.** If all versions are rejected, GET /node/{id} returns the node with status "rejected". Not 404 — the node exists.
3. **No rollback mechanism.** To restore v1 after v2 was promoted: create v3 with v1's code, promote v3. Explicit, auditable, visible in history. This is by design.
4. **Breaking changes are OK.** No external consumers. build.py will be adapted after verification.
5. **task_id is free text.** No validation, no external table. Format will be decided when coordinator exists.

## Execution constraint

Experiments are running on CodeGraph instances (ports 39053-39055). Do NOT restart the main CodeGraph on port 39051 until experiments complete. Phase 1 = write all code changes + migration logic. Phase 2 (after experiments) = restart, migrate, verify. Write code now, test later.

## Subagent guidance

This is a modification of existing code, not new code. You need to understand the current db.py, main.py, models.py before changing them. Read them first. The migration logic and the version selection layer (golden-first, fallback to draft) are the critical pieces — do those yourself.
