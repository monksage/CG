# Report: Add Version System to CodeGraph

## Result
Done.

## What was built
- `versions` table added to schema (node_id, version, code, specs, contracts, task_id, status, created_at).
- Idempotent migration: all existing nodes (66) get version 1 as golden on startup.
- Nodes table retained as cache of active version. Sync on promote, reject, and draft-when-no-golden.
- New endpoints: POST /node/{id}/version, POST /node/{id}/promote, POST /node/{id}/reject, GET /node/{id}/versions, GET /node/{id}/version/{n}.
- PUT /node/{id} removed.
- POST /node now creates node + version 1 as draft. status field removed from NodeCreate input.
- DELETE /node explicitly deletes versions before the node (no CASCADE).
- build.py verified — no changes needed, reads golden via GET /node/{id}.

## Deviations from order
- Added `_sync_version_to_node` helper in db.py. Order says no helpers unless required — this one is required, used by promote, reject, and create_version. Three callers, not premature.

## Verification
1. GET /node/process_signal → version=1, status=golden — **pass**
2. GET /node/process_signal/versions → v1 golden, task_id=migration — **pass**
3. POST /node test_versioning → version=1, status=draft — **pass**
4. GET /node/test_versioning → returns draft (no golden yet) — **pass**
5. POST /node/test_versioning/promote → version=1, status=golden — **pass**
6. POST /node/test_versioning/version (v2) → version=2, status=draft — **pass**
7. GET /node/test_versioning → returns v1 golden, not v2 draft — **pass**
8. POST /node/test_versioning/promote → version=2, status=golden — **pass**
9. GET /node/test_versioning/versions → v1 deprecated, v2 golden — **pass**
10. GET /context/process_signal → target=process_signal, 67 nodes — **pass**
11. PUT /node/test_versioning → 405 Method Not Allowed — **pass**
12. MCGK route codegraph/node/process_signal → version=1, status=golden — **pass**

Test node cleaned up after verification.

## Open issues
None.
