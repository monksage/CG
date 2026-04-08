# Report: Decompose Code Into Graph Nodes

## Result
Done.

## What was built
24 nodes loaded into CodeGraph from the Nightmare Service (proxy stress-test). No edges — all endpoints are independent with no inter-function calls.

**Contour nodes (7) — decision-bearing:**

| Node | Decision type |
|------|--------------|
| `negotiate_content` | if/elif/else on Accept header (4 branches) |
| `resolve_status_code` | if/elif/else on status code (5 branches) |
| `build_binary_blob` | for loop packing binary data |
| `stream_chunks` | for loop + async yield (20 chunks) |
| `stream_ndjson` | for loop + async yield (10 NDJSON lines) |
| `stream_slow_sse` | for loop + async yield + sentinel |
| `check_conditional_etag` | if/else on ETag match |

**Micro nodes (17) — no decisions:**

| Node | Original endpoint |
|------|------------------|
| `check_health` | `/health` |
| `echo_headers` | `/echo-headers` |
| `echo_large_body` | `/large-body` |
| `receive_multipart` | `/multipart-mixed` |
| `emit_duplicate_headers` | `/duplicate-headers` |
| `return_empty_response` | `/empty-204` |
| `redirect_permanent` | `/redirect` |
| `echo_query_string` | `/echo-query` |
| `echo_request_body` | `/echo-body` |
| `handle_route_collision` | `/route/nested/path` |
| `handle_register_collision` | `/register` |
| `serve_unicode_path` | `/unicode/путь/データ` |
| `handle_head_request` | `/head-test` (HEAD + GET) |
| `serve_partial_content` | `/partial-206` |
| `handle_mismatched_type` | `/mismatched-content-type` |
| `decode_encoded_path` | `/encoded/{segment}` |
| `serve_root` | `/` |

## Deviations from order
None.

## Verification
1. `GET /graph` returns 24 node ids, 0 edges — **pass**
2. Leaf node `serve_root` context: depth 0 = full code + all specs, all others depth 999 (name only, disconnected) — **pass**
3. "Central node" test: not meaningful — no edges exist, so all nodes are equally disconnected. Every context query shows the same pattern: depth 0 full, rest depth 999 — **pass** (expected for edgeless graph)
4. Node count: 24 loaded = 24 planned (7 contour + 17 micro) — **pass**

## Open issues
1. **Zero edges.** The Nightmare Service is a flat collection of independent HTTP endpoints — no function calls another. The resulting graph is 24 disconnected nodes. This is a valid but uninteresting test for Dunbar circles. A codebase with actual call chains would exercise the context endpoint better.
2. **Micro nodes as standalone.** The decomposition rules say micros should be "inlined into the parent node," but these endpoints have no parent — they are all top-level handlers. Created them as standalone micro nodes since there is nothing to inline them into.
